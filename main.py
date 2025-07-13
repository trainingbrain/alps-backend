from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
import shutil, os, tempfile, zipfile, subprocess
import nibabel as nib
import numpy as np
import uuid

app = FastAPI(title="ALPS-Index Calculation Server", version="1.0.0")

# --- İşlerin durumunu ve sonuçlarını saklamak için global bir sözlük ---
# Gerçek bir uygulamada bu bir veritabanı olurdu, ama prototip için yeterli.
JOBS = {}

# --- Tüm FSL/MRtrix3 işlemleri artık bu tek fonksiyonda ---
def run_pipeline(job_id: str, zip_file_path: str):
    """
    Bu fonksiyon arka planda çalışır, tüm ağır işlemleri yapar
    ve sonucu JOBS sözlüğüne yazar.
    """
    temp_dir = tempfile.mkdtemp()
    pipeline_log = []
    
    # İşin durumunu "çalışıyor" olarak güncelle
    JOBS[job_id] = {"status": "running", "log": pipeline_log}
    
    try:
        # --- BURADAN İTİBAREN TÜM ÖN-İŞLEME VE HESAPLAMA MANTIĞI ---
        # (Bu blok, daha önceki başarılı kodumuzun aynısıdır)
        
        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        os.remove(zip_file_path) # Geçici zip dosyasını silebiliriz

        nifti_output_dir = os.path.join(temp_dir, "nifti_output")
        os.makedirs(nifti_output_dir)
        run_command(["dcm2niix", "-o", nifti_output_dir, "-z", "y", "-b", "y", "-f", "%d_%p_%s", temp_dir], pipeline_log)
        
        found_files = find_files_robustly(nifti_output_dir, pipeline_log)
        if not found_files["main_dti"]: raise Exception("Ana DTI dosyası bulunamadı.")
        
        processed_dti_info = found_files["main_dti"]
        
        if found_files["ap_b0"] and found_files["pa_b0"]:
            # ... topup ve eddy mantığı ...
            pipeline_log.append("AP ve PA b0 dosyaları bulundu. Tam bozulma düzeltme uygulanacak.")
            # ... (Bu bloklar önceki koddan alınacak) ...
            pipeline_log.append("Eddy ile tam bozulma düzeltme tamamlandı.")
        else:
            pipeline_log.append("AP/PA b0 dosyaları bulunamadı, bozulma düzeltme atlanıyor.")

        # ... dtifit ve fslroi adımları ...
        pipeline_log.append("Dxx, Dyy, Dzz haritaları oluşturuldu.")

        alps_mean, details = calculate_alps_index(nifti_output_dir)
        pipeline_log.append("ALPS İndeksi başarıyla hesaplandı.")
        
        # İş bittiğinde sonucu ve durumu güncelle
        JOBS[job_id]["status"] = "completed"
        JOBS[job_id]["result"] = {
            "alps_index_mean": alps_mean,
            "alps_index_left": details["left_hemisphere"]["alps_index"],
            "alps_index_right": details["right_hemisphere"]["alps_index"],
            "calculation_details": details
        }

    except Exception as e:
        # Hata durumunda durumu ve hata mesajını güncelle
        JOBS[job_id]["status"] = "failed"
        JOBS[job_id]["error"] = str(e)
    finally:
        shutil.rmtree(temp_dir)

# --- Yardımcı Fonksiyonlar (run_command, get_nifti_dims vb.) ---
# ... (Bu fonksiyonları da önceki koddan buraya kopyalayın) ...
def run_command(command, log_list, cwd=None):
    log_list.append(f"Çalıştırılıyor: {' '.join(command)}")
    result = subprocess.run(command, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        error_message = f"Komut hatası: {command[0]}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        log_list.append(error_message)
        raise Exception(error_message)
    log_list.append(f"{command[0]} başarıyla tamamlandı.")
    return result
# ... (get_nifti_dims, find_files_robustly, calculate_alps_index)

# --- FastAPI Endpoint'leri ---

@app.post("/start-processing")
def start_processing(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Dosyayı alır, işi arka plana atar ve bir iş ID'si döndürür."""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            temp_file_path = temp_file.name
        
        job_id = str(uuid.uuid4())
        JOBS[job_id] = {"status": "queued"}
        
        background_tasks.add_task(run_pipeline, job_id, temp_file_path)
        
        return {"message": "İşlem başarıyla başlatıldı.", "job_id": job_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status/{job_id}")
def get_status(job_id: str):
    """Verilen iş ID'sinin durumunu ve sonucunu döndürür."""
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="İş ID'si bulunamadı.")
    return job