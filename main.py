from fastapi import FastAPI, UploadFile, File
import redis
from rq import Queue
import uuid
from worker import process_dti_pipeline # Ağır işi yapacak fonksiyonu import ediyoruz

# Redis bağlantısı
redis_conn = redis.from_url(os.environ.get("REDIS_URL"))
q = Queue('alps-pipeline-queue', connection=redis_conn)

app = FastAPI(title="ALPS-Index Calculation Server")

@app.post("/process")
def queue_job(file: UploadFile = File(...)):
    """Dosyayı alır, geçici bir yere kaydeder ve işi kuyruğa ekler."""
    try:
        # Dosyayı geçici olarak kaydet
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            temp_file_path = temp_file.name
        
        # İşi kuyruğa ekle ve bir ID al
        job = q.enqueue(process_dti_pipeline, temp_file_path)
        
        return {"job_id": job.get_id()}
    except Exception as e:
        return {"error": str(e)}

@app.get("/results/{job_id}")
def get_results(job_id: str):
    """Verilen iş ID'sinin sonucunu döndürür."""
    job = q.fetch_job(job_id)
    if job:
        if job.is_finished:
            return {"status": "tamamlandı", "result": job.result}
        elif job.is_failed:
            return {"status": "hata", "error": job.exc_info}
        else:
            return {"status": "çalışıyor"}
    return {"status": "bulunamadı"}