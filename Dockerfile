# Web Aracı için Optimize Edilmiş Dockerfile
FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive

# FSL ve MRtrix3'ün çalışması için gereken temel sistem kütüphaneleri
RUN apt-get update && apt-get install -y --no-install-recommends \
    git wget procps libgl1-mesa-glx \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Miniconda'yı kuruyoruz
ENV CONDA_DIR /opt/conda
RUN wget --quiet https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda.sh && \
    /bin/bash ~/miniconda.sh -b -p /opt/conda
ENV PATH=$CONDA_DIR/bin:$PATH

# Gerekli araçları Conda ile kuruyoruz
RUN conda install -c mrtrix3 mrtrix3 -y

# FSL'i kendi yükleyicisi ile kuruyoruz
ENV FSLDIR="/usr/local/fsl"
ENV FSLOUTPUTTYPE="NIFTI_GZ"
ENV PATH=${FSLDIR}/bin:${PATH}
RUN wget https://fsl.fmrib.ox.ac.uk/fsldownloads/fslinstaller.py -P /tmp/ && \
    python /tmp/fslinstaller.py -d ${FSLDIR}

# Uygulamamızın Python kütüphanelerini kuruyoruz
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama kodumuzu kopyalıyoruz
WORKDIR /app
COPY main.py .

# Sunucuyu başlatıyoruz
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
