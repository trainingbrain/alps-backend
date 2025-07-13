FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    build-essential git wget unzip python3 python3-pip python3-numpy \
    libeigen3-dev zlib1g-dev libgl1-mesa-dev libglu1-mesa-dev \
    qtbase5-dev libqt5svg5-dev libtiff-dev libpng-dev libfftw3-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN ln -s /usr/bin/python3 /usr/bin/python

RUN git clone https://github.com/MRtrix3/mrtrix3.git /opt/mrtrix3
WORKDIR /opt/mrtrix3
RUN ./configure && ./build

ENV FSLDIR=/opt/fsl
ENV FSLOUTPUTTYPE=NIFTI_GZ
RUN wget https://fsl.fmrib.ox.ac.uk/fsldownloads/fslinstaller.py -P /tmp/ && \
    python3 /tmp/fslinstaller.py -d ${FSLDIR}

ENV PATH=${FSLDIR}/bin:/opt/mrtrix3/bin:${PATH}

WORKDIR /app
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt
COPY main.py .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]