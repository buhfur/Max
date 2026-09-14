# Changes 

This file documents every change I make to max's capabilities / commands they can run 


* allowed nmap command by through setcap 
```bash
sudo setcap cap_net_raw,cap_net_admin,cap_net_bind_service+eip "$(command -v nmap)"
```

* allowed netstat commands through setcap 
