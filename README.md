

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
