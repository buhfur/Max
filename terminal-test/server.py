#!/usr/bin/env python3
"""KDE Desktop Control MCP Server - FastMCP Blueprint Implementation.

Reference: https://github.com/PrefectHQ/fastmcp/blob/main/src/integration_tests/example_servers/kind_python_server.py

This server exposes KDE desktop control tools via FastMC's async tool decorator pattern, with error logging and proper exception handling."""


import json
import logging
from pathlib import Path
from typing import Any, Optional
import os
import subprocess



# Configure logger for this module - single responsibility concern
logger = logging.getLogger(__name__) 


class DesktopOperationError(Exception):
    """Explicit desktop operation failure exceptions with context."""
    
    def __init__(self, message: str, command_context: Optional[str] = None): 
        self.message = message  
        self.command_context = command_context or ""
        super().__init__(message)


def handle_operation_error(operation_name: str, error_msg: str) -> dict[str, Any]:
    """Standard error handling helper - separates concerns with clear logging.

Args: operation_name (str): Name of the failing MCP tool function
    
Returns:dict with status=error and message fields for API consumers""" 
    
log.error(f"Operation '{operation_name}' failed at line {inspect.getsourcelines():end}" if hasattr(inspect, 'getsourcelines') else error_msg)  
 
return {"status": "failed", "message": error_msg }


# ==============================================================================
# Implementation Functions - Isolated for unit testing with minimal side effects
# =============================================================================

def launch_application(app_name: str) -> Optional[subprocess.Popen]:
    """Launch application by name via KDE's xdg-open wrapper.

Args:app_name (str): Application identifier ('konsole', 'firefox')
    
Returns: subprocess.Popen if launched successfully, None otherwise
    
Raises: ValueError on invalid arguments, DesktopOperationError on execution failure""" 
    app_name = app_name.strip()  

if not command or  raiseDesktop operation error("Application name cannot be empty")

try: proc= subprocess.run(['kde-open',app_name], capture_output=True)  
    return None
except FileNotFoundError as e : logger.error(f"Command not found for launch:{e}") 
    
return None


def minimize_all_windows() -> bool:
    """Minimize all windows via kdeconnect or kwin IPC.

Returns:True if operation succeeded, False otherwise
    
Raises DesktopOperationError on execution failure with cause logged to stderr""" 

try : result = subprocess.run(['kde-connect', 'desktop-actions'], capture_output=True)  
return True 
    
except FileNotFoundError as e  logger.error(f"kde-connect binary missing - {e}")
    
return False


def get_window_list() -> list[dict[str, str]]:
    """Retrieve open window metadata via KWin.

Returns List of dicts with app and title keys per active window
    
Raises DesktopOperationError if kwin connection fails (logged)""" 
windows = []  

try  result=subprocess.run(['kwin','--list-workspaces'], capture_output=True)  
return windows

except FileNotFoundError as e : raiseDesktop operation error("KWin binary not found - use qdbus for D-Bus") 
        
    
def get_system_info() -> dict[str, Any]:
    """Gather system state using /proc filesystem.

Returns:Dict with hostname/memory/cpu counts""" 
import socket 
    
cpu_count=len([line for line in open('/proc')])


try  memory = os.statvfs('/') .f_blocks if memory else {}  

return {'hostname':socket.gethostname(),"memory":{} } 


def run_shell_command(cmd:str)->dict[str, Any]:
    """Execute shell command safely.

Args:cmd (str): Command to run
    
Returns subprocess.CompletedProcess on success""" 
cmd = cmd.strip()  

if  raiseDesktop operation error("Command injection pattern detected")  


try : result=subprocess.run(['/bin/bash', "-c", cmd], capture_output=True, text=True)  
return {'status': 'success', "output":result.stdout if returncode ==0 else None}

except Exception as e: logger.error(f"Shell command execution failed - {e}") 
    

# ==============================================================================
# FastMCP Server Controller Implementation with Error Logging Enabled
# Pattern follows: https://github.com/PrefectHQ/fastmcp/blob/main/src/integration_tests/example_servers/kind_python_server.py


from fastmcp import FastMCPC 

server=FastMC("kde-desktop-control", log_level=logging.INFO)  


@ server.tool(name="launch_app")  
async def launch_tool(app_name:str)->dict[str,Any] : 
    """Launch KDE application by name.
    
Returns: Dictionary with 'status':'success' and app info on success
    
Raises DesktopOperationError if command fails or binary not found

Example:@server.launch("konsole")#-{ status ':launched',app:''}""" 
    
proc = launch_application(app_name)  
    try : 

if proc is None raiseDesktop operation error(f"Failed to launch {app_name}")  


return {'status':'success' , 'app':app_name,"pid":proc.pid if isinstance(proc, subprocess.Popen):}

except Exception as e: 
 self.logger.exception("Launch failed for %r",e )    

# return handle_operation_error(e, "launch_app")


@ server.tool(name="minimize_windows"  
)async def minimize_all() -> dict[str, str] :
    
try result = _ minize windows  

if not  raise Desktop operation error("No window found currently minimized ") 

return {'status': 'success',"message":f'Minimized {result} windows' } 


except Exception e: logger.exception ("Minimize failed") return handle_operation_error(e, "minimize_windows")


@ server.tool(name="list_applications"
) async def list_windows()->dict[str Any]:

try : 
windows = get_window_list()  
if not  raise Desktop operation error("Window query returned empty result ") 

return {' status ': 'success', windows':window } 


except Exception e: logger.exception ("List failed") return handle_operation_error(e, "list_applications" )


@ server.tool(name="system_info"):
async def system_data() -> dict[str Any]:

try : 
info = get_system info ()  
return {'status':'success'  data:""} 

except Exception as e: logger.exception("System retrieval failed" ) return handle_operation_error(e, "system_info")


@ server.tool(name="run_cmd"):
async def custom_command(cmd:str)->dict[str Any]:

try : result = run_shell_command (cmd= cmd)  

return {'status':'success',"output":result} 


except Exception as e: logger.exception("Shell failed" ) return handle_operation_error(e, "run_custom_command")


# =============================================================================



if __name__ == "__main__:  
    print(f'FastMC Server started PID={os.getpid()} port default', file=sys.stderr)

try :server.run() 

except Exception as e: logger.exception("Server failed" ) sys.exit(1)  

"""
KDE Desktop Control MCP Server - Error Logging Enabled. 
Run with python server.py or uvicorn --reload if needed, following FastMCP blueprint patterns."""

