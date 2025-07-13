from fastapi import FastAPI, UploadFile, File, HTTPException
import shutil, os, tempfile, zipfile, subprocess
import nibabel as nib
import numpy as np

app = FastAPI(title="ALPS-Index Calculation Server (Simple Pipeline)", version="1.0-web")

def run_command(command, log_list, cwd=None):
    """Verilen komutu, Render.com ortamıyla uyumlu olacak şekilde çalıştırır."""
    command_str = ' '.join(command)
    log_list.append(f"Çalıştırılıyor: {command_str}")
    result = subprocess.run(command_str, shell=True, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        error_message = f"Komut hatası: {command[0]}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        log_list.append(error_message)
        raise Exception(error_message)
    log_list.append(f"{command[0]} başarıyla tamamlandı.")
    return result

def get_nifti_dims(file_path, log_list):
    """fslinfo kullanarak bir nifti dosyasının boyutlarını döndürür."""
    result = run_command(["fslinfo", file_path], log_list)
    dims = {}
    for line in result.stdout.splitlines():
        if line.startswith("dim"): parts = line.split(); dims[parts[0]] = int(parts[1])
    return dims

def find_main_dti(nifti_dir, log_list):
    """Klasördeki en çok hacme sahip ve bvec/bval dosyaları olan DTI setini bulur."""
    main_dti_info = None
    max_vols = 0
    all_nifti_files = [f for f in os.listdir(nifti_dir) if f.endswith('.nii.gz')]
    for f in all_nifti_files:
        full_path = os.path.join(nifti_dir, f)
        base_name = f.replace(".nii.gz", "")
        bvec_path = os.path.join(nifti_dir, base_name + ".bvec")
        bval_path = os.path.join(nifti_dir, base_name + ".bval")
        if os.path.exists(bvec_path) and os.path.exists(bval_path):
            dims = get_nifti_dims(full_path, log_list)
            num_vols = dims.get("dim4", 1)
            if num_vols > max_vols:
                max_vols = num_vols
                main_dti_info = {"path": full_path, "bvec": bvec_path, "bval": bval_path, "dims": dims}
    return main_dti_info

def calculate_alps_index(nifti_dir):
    """Verilen klasördeki dxx, dyy, dzz haritalarından ALPS indeksini hesaplar."""
    details = {}
    try:
        dxx_map = nib.load(os.path.join(nifti_dir, "dxx.nii.gz")).get_fdata()
        dyy_map = nib.load(os.path.join(nifti_dir, "dyy.nii.gz")).get_fdata()
        dzz_map = nib.load(os.path.join(nifti_dir, "dzz.nii.gz")).get_fdata()
    except FileNotFoundError:
        raise Exception("Hesaplama için gereken dxx, dyy veya dzz dosyaları bulunamadı.")
    img_dims = dxx_map.shape; cx, cy, cz = img_dims[0] // 2, img_dims[1] // 2, img_dims[2] // 2
    rois = { "proj_R": (cx + 15, cy, cz), "assoc_R": (cx - 15, cy, cz), "proj_L": (cx - 15, cy, cz), "assoc_L": (cx + 15, cy, cz) }
    def get_roi_mean(volume, center_coord):
        x, y, z = [int(c) for c in center_coord]; return np.mean(volume[x-1:x+2, y-1:y+2, z-1:z+2])
    vals = {
        "dxx_proj_R": get_roi_mean(dxx_map, rois["proj_R"]), "dxx_assoc_R": get_roi_mean(dxx_map, rois["assoc_R"]),
        "dyy_assoc_R": get_roi_mean(dyy_map, rois["assoc_R"]), "dzz_proj_R": get_roi_mean(dzz_map, rois["proj_R"]),
        "dxx_proj_L": get_roi_mean(dxx_map, rois["proj_L"]), "dxx_assoc_L": get_roi_mean(dxx_map, rois["assoc_L"]),
        "dyy_assoc_L": get_roi_mean(dyy_map, rois["assoc_L"]), "dzz_proj_L": get_roi_mean(dzz_map, rois["proj_L"]),
    }
    num_R = np.mean([vals["dxx_proj_R"], vals["dxx_assoc_R"]]); den_R = np.mean([vals["dyy_assoc_R"], vals["dzz_proj_R"]])
    num_L = np.mean([vals["dxx_proj_L"], vals["dxx_assoc_L"]]); den_L = np.mean([vals["dyy_assoc_L"], vals["dzz_proj_L"]])
    if den_R == 0 or den_L == 0: raise ValueError("ALPS indeksi hesaplanırken payda sıfır oldu.")
    alps_R = num_R / den_R; alps_L = num_L / den_L
    details["right_hemisphere"] = {"alps_index": alps_R, "components": {k: v for k, v in vals.items() if k.endswith("_R")}}
    details["left_hemisphere"] = {"alps_index": alps_L, "components": {k: v for k, v in vals.items() if k.endswith("_L")}}
    return np.mean([alps_R, alps_L]), details

@app.get("/")
def read_root(): return {"message": "ALPS-Index Web Aracı (Basit Pipeline) çalışıyor."}

@app.post("/process-dti/")
async def process_dti_data(file: UploadFile = File(...)):
    temp_dir = tempfile.mkdtemp()
    pipeline_log = []
    try:
        zip_path = os.path.join(temp_dir, file.filename)
        with open(zip_path, "wb") as buffer: shutil.copyfileobj(file.file, buffer)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref: zip_ref.extractall(temp_dir)
        nifti_output_dir = os.path.join(temp_dir, "nifti_output"); os.makedirs(nifti_output_dir)
        run_command(["dcm2niix", "-o", nifti_output_dir, "-z", "y", "-b", "y", "-f", "%d_%p_%s", temp_dir], pipeline_log)
        main_dti_info = find_main_dti(nifti_output_dir, pipeline_log)
        if not main_dti_info: raise HTTPException(status_code=404, detail="Ana DTI dosyası ve bvec/bval dosyaları bulunamadı.")
        
        processed_dti_info = main_dti_info
        
        # Hafif Ön-İşleme
        denoised_path = os.path.join(nifti_output_dir, "dwi_denoised.nii.gz"); run_command(["dwidenoise", processed_dti_info["path"], denoised_path], pipeline_log)
        unringed_path = os.path.join(nifti_output_dir, "dwi_denoised_unringed.nii.gz"); run_command(["mrdegibbs", denoised_path, unringed_path], pipeline_log)
        processed_dti_info["path"] = unringed_path; pipeline_log.append("Denoise ve Unringing tamamlandı.")

        pipeline_log.append("BİLGİ: Hızlı analiz için ağır bozulma düzeltme (topup/eddy) adımları atlandı.")

        # Ortak Adımlar
        b0_for_bet_path = os.path.join(nifti_output_dir, "b0_for_bet.nii.gz"); run_command(["fslroi", processed_dti_info["path"], b0_for_bet_path, "0", "1"], pipeline_log)
        mask_base_path = os.path.join(nifti_output_dir, "dwi_brain"); run_command(["bet", b0_for_bet_path, mask_base_path, "-m", "-f", "0.3"], pipeline_log)
        mask_path = mask_base_path + "_mask.nii.gz"; pipeline_log.append("BET ile beyin maskesi oluşturuldu.")
        
        dti_output_base = os.path.join(nifti_output_dir, "dti")
        run_command([ "dtifit", f"--data={processed_dti_info['path']}", f"--out={dti_output_base}", f"--mask={mask_path}", f"--bvecs={processed_dti_info['bvec']}", f"--bvals={processed_dti_info['bval']}", "--save_tensor"], pipeline_log); pipeline_log.append("dtifit ile tensör uydurma tamamlandı.")
        
        tensor_path = dti_output_base + "_tensor.nii.gz"
        run_command(["fslroi", tensor_path, os.path.join(nifti_output_dir, "dxx.nii.gz"), "0", "1"], pipeline_log)
        run_command(["fslroi", tensor_path, os.path.join(nifti_output_dir, "dyy.nii.gz"), "3", "1"], pipeline_log)
        run_command(["fslroi", tensor_path, os.path.join(nifti_output_dir, "dzz.nii.gz"), "5", "1"], pipeline_log)
        pipeline_log.append("Dxx, Dyy, Dzz haritaları oluşturuldu.")

        alps_mean, details = calculate_alps_index(nifti_output_dir)
        pipeline_log.append("ALPS İndeksi başarıyla hesaplandı.")

        return { "status": "ALPS indeksi başarıyla hesaplandı (Basit Pipeline)", "alps_index_mean": alps_mean, "alps_index_left": details["left_hemisphere"]["alps_index"],
                 "alps_index_right": details["right_hemisphere"]["alps_index"], "calculation_details": details, "log": pipeline_log }
    except Exception as e:
        raise HTTPException(status_code=500, detail={"log": pipeline_log, "error": str(e)})
    finally:
        shutil.rmtree(temp_dir)
