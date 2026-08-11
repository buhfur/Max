

# Max , my personal assistant 


Can do the following : 

* Run tests on code :

* spin up dev environments

* Acess to filesystem for read / write / execute operations  ( with limited control )

* security scans 

* Interactive voice with wake word 

* runs in background , with system tray and 

* floating assistant, system tray behavior, overlays on top of applications, 

* screen-aware interaction, 

* global keyboard shortcuts, 

* custom wake-word indicators, 

* highly customized terminal/code panes 

Proof of concept video : 
<img src="https://archive.org/embed/spiderman-clip" alt="Description" width="400" align="center" />

<iframe src="https://archive.org/embed/spiderman-clip" width="560" height="384" frameborder="0" webkitallowfullscreen="true" mozallowfullscreen="true" allowfullscreen></iframe>


# Setup for AMD card 

1. add the 2 environment variables at the end of your activate script , these two environment variables are used with cTranslate2 compiled with ROCM support 

```bash
# for 6800 XT radeon card
export HSA_OVERRIDE_GFX_VERSION=10.3.0
export AMDGPU_TARGETS=gfx1030
```

2. isntall cTranslate2 wheels with compiled ROCM support 

```bash
# https://github.com/OpenNMT/CTranslate2/releases/download/v4.7.1/rocm-python-wheels-Linux.zip
# For python3.12 
pip install ctranslate2-4.7.1-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl
```

```bash
sudo apt install -y rocminfo rocm-smi
sudo usermod -a -G render,video $USER
```

3. Installed PyTorch with rocm6.2 support 
```bash
pip3 install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/rocm6.2/
```

4. installed dependencies for AMD ROCM support 

I had some issues with my system , used google gemini to help me clean it up and get the right packages. Below are just all the commands I used 
```bash
# install amdgpu-install 
wget https://repo.radeon.com/amdgpu-install/6.2/ubuntu/noble/amdgpu-install_6.2.60200-1_all.deb

# Install package 
dpkg -i amdgpu-install_6.2.60200-1_all.deb
# Build ROCM 6.2 compute engine 
sudo apt update
sudo amdgpu-install --usecase=rocm --no-dkms
sudo apt-get autoremove --purge rocminfo
sudo apt update
sudo apt install -y rocminfo=1.0.0.60200-66~24.04
sudo amdgpu-install --usecase=rocm --no-dkms
echo 'export HSA_OVERRIDE_GFX_VERSION=10.3.0' >> ~/.zshrc
echo 'export PATH=$PATH:/opt/rocm/bin' >> ~/.zshrc
source ~/.zshrc

sudo apt-get purge -y rocminfo
sudo apt-get autoremove -y

# I think I fixed it by just changing the permissions for /dev/kfd and /dev/dri/renderD*
# Possibly just because I didn't restart and only logged out so the group permissions didn't 
# take effect.....*sigh*
sudo chmod 666 /dev/kfd
sudo chmod 666 /dev/dri/renderD*

# Still getting import error from ctranslate2 
sudo apt update
sudo apt install -y hiprand hiprand-dev

# update dynamic linker paths 
export LD_LIBRARY_PATH=/opt/rocm/lib:$LD_LIBRARY_PATH

# make path and GPU targets perma
# I keep my exports in another file which is sourced by ~/.zshrc 
echo 'export HIP_VISIBLE_DEVICES=0' >> ~/.exports
echo 'export HSA_OVERRIDE_GFX_VERSION=10.3.0' >> ~/.exports
echo 'export LD_LIBRARY_PATH=/opt/rocm/lib:$LD_LIBRARY_PATH' >> ~/.exports
source ~/.zshrc

#  Install hipBLAS from the Connected AMD Repository
sudo apt update
sudo apt install -y hipblas hipblas-dev

# Create symlink to libhipblas.so.3 
sudo ln -s /opt/rocm/lib/libhipblas.so.2 /opt/rocm/lib/libhipblas.so.3

# update runtime linker cache 
sudo ldconfig 

# find symlinks or some shit 
ls -lh /opt/rocm/lib/libamdhip64.so*

# Create symlinks 
sudo ln -s /opt/rocm/lib/libamdhip64.so.6 /opt/rocm/lib/libamdhip64.so.7
sudo ldconfig

# Install missing rocrand packages 
sudo apt update
sudo apt install -y rocrand rocrand-dev

# Finally , no more ctranslate2 errors 

# rocm-smi is outdated , use amd-smi 
sudo apt install amd-smi-lib
```
