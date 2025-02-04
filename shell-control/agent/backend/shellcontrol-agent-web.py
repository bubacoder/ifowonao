from typing import Dict
from shellcontrol import ShellAgent, Event
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from traceback import format_exc
import asyncio
import psutil
import os


DEBUG = os.getenv('DEBUG', '0').lower() in ('true', '1')

app = FastAPI(title='shellcontrol.py')


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        # Receive user prompt from the frontend
        user_event = await websocket.receive_json()
        
        if user_event["type"] != "prompt":
            print(f"Unhandled user event type: {user_event["type"]}", flush=True)
            return

        prompt = user_event["payload"].strip()
        print(f"Received prompt: {prompt}", flush=True)

        agent = ShellAgent()
        async for event in agent.process_user_request(prompt):
            event_type: Event = event["type"]
            event_payload = event["payload"]

            if event_type == Event.COMPLETED:
                event_payload = agent.get_usage_summary()

            # Send event back to the client
            event_to_send = {
                "type": event_type.name,
                "payload": event_payload
            }
            print(f"Sending: {event_type.name}", flush=True)
            await websocket.send_json(event_to_send)
            # Small delay to allow the WebSocket to flush its buffer
            await asyncio.sleep(0.1)

            if event_type == Event.COMPLETED:
                await websocket.close()
                break

    except Exception as ex:
        exception_text = format_exc() if DEBUG else str(ex)
        print(exception_text, flush=True)


@app.get("/health")
async def health_endpoint() -> Dict[str, str]:
    return {"status": "OK"}


@app.post("/terminate")
def terminate_endpoint() -> Dict[str, str]:
    """
    Forcefully terminates all child processes and the server itself.
    """
    try:
        # Get the current process
        current_process = psutil.Process(os.getpid())

        # Terminate child processes
        for child in current_process.children(recursive=True):
            print(f"Terminating child process {child.pid}...")
            child.terminate()  # Send terminate signal

        # Allow some time for graceful termination
        gone, alive = psutil.wait_procs(current_process.children(), timeout=5)

        # If any processes are still alive, force kill them
        for process in alive:
            print(f"Killing child process {process.pid}...")
            process.kill()

        # Finally, terminate the main server process
        print("Terminating the web server...")
        os._exit(0)  # Exit the server process

    except Exception as ex:
        if DEBUG:
            return {"status": "error", "detail": format_exc()}
        return {"status": "error", "detail": str(ex)}

    # Good luck with sending this message...
    return {"status": "success", "message": "All processes terminated, including the server."}


# Mount the Vue.js frontend build folder as static files
app.mount("/", StaticFiles(directory="frontend", html=True))
