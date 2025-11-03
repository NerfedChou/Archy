from fastapi import FastAPI, HTTPException
import subprocess
import os
import platform
import shutil

app = FastAPI()

@app.get("/execute_command/")
def execute_command(command: str):
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return {"stdout": result.stdout, "stderr": result.stderr}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/file_access/")
def file_access(filename: str, mode: str = 'r', content: str = None):
    if mode == 'r':
        if not os.path.exists(filename):
            raise HTTPException(status_code=404, detail="File not found")
        with open(filename, 'r') as file:
            return {"content": file.read()}
    elif mode == 'w':
        with open(filename, 'w') as file:
            file.write(content)
        return {"message": "File written successfully"}
    else:
        raise HTTPException(status_code=400, detail="Invalid mode")

@app.get("/check_tool/")
def check_tool(tool_name: str):
    tool_found = shutil.which(tool_name) is not None
    return {"tool_found": tool_found}

@app.get("/system_info/")
def system_info():
    system_info = {
        "platform": platform.system(),
        "platform_release": platform.release(),
        "architecture": platform.architecture(),
        "hostname": platform.node(),
        "cpu": os.cpu_count(),
    }
    return system_info

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)