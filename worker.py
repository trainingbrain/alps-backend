import shutil, os, tempfile, zipfile, subprocess
import nibabel as nib
import numpy as np

# Bu dosya, main.py'deki tüm run_command, get_nifti_dims, 
# find_files_robustly, calculate_alps_index gibi yardımcı
# fonksiyonları ve asıl pipeline mantığını içerir.

def run_command(command, cwd=None):
    print(f"Worker çalıştırıyor: {' '.join(command)}")
    result = subprocess.run(command, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        error_message = f"Komut hatası: {command[0]}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        print(error_message)
        raise Exception(error_message)
    print(f"{command[0]} başarıyla tamamlandı.")
    return result

# ... (Bir önceki main.py'deki get_nifti_dims, find_files_robustly, calculate_alps_index fonksiyonlarını buraya kopyalayın) ...
def get_nifti_dims(file_path):
    # ...
    pass
def find_files_robustly(nifti_dir):
    # ...
    pass
def calculate_alps_index(nifti_dir):
    # ...
    pass

def process_dti_pipeline(zip_file_path):
    """
    Bu fonksiyon, bir işçi (worker) tarafından çağrılır ve tüm ağır işi yapar.
    """
    temp_dir = tempfile.mkdtemp()
    pipeline_log = []
    try:
        # ... (Bir önceki main.py'deki /process-dti/ fonksiyonunun içindeki
        # tüm try bloğunun mantığı buraya gelecek) ...
        
        # Örnek başlangıç:
        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # ... dcm2niix, topup, eddy, dtifit, calculate_alps_index...
        # tüm adımlar burada çalıştırılır.
        
        # Örnek sonuç:
        final_result = {
            "status": "Tamamlandı",
            "alps_index_mean": 1.2345
        }
        return final_result

    except Exception as e:
        return {"status": "Hata", "error": str(e)}
    finally:
        shutil.rmtree(temp_dir)