import time
import os

pipe_path = "/tmp/mcp_pipe"

if not os.path.exists(pipe_path):
    os.mkfifo(pipe_path)

with open(pipe_path, "w") as f:
    while True:
        f.write("ping\n")
        f.flush()
        time.sleep(10)
