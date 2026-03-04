# import psutil
# import time
# import socket
# import psycopg
# from datetime import datetime

# DB_CONFIG = {
#     "host": "65.108.232.96",
#     "dbname": "mydb",
#     "user": "myuser",
#     "password": "strongpassword",
#     "port": 5432
# }

# INTERVAL = 30  # seconds

# # ---------------------------
# # get local IP
# # ---------------------------
# def get_local_ip():
#     s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#     s.connect(("8.8.8.8", 80))
#     ip = s.getsockname()[0]
#     s.close()
#     return ip

# # ---------------------------
# # get process list from DB
# # ---------------------------
# def get_process_list(local_ip):
#     with psycopg.connect(**DB_CONFIG) as conn:
#         with conn.cursor() as cur:
#             cur.execute("""
#                 SELECT process_name
#                 FROM sn71_process
#                 WHERE ip = %s
#             """, (local_ip,))
#             rows = cur.fetchall()
#     return [r[0] for r in rows]

# # ---------------------------
# # find process by name
# # ---------------------------
# def find_process(name):
#     for p in psutil.process_iter(['name', 'status']):
#         try:
#             if p.info['name'] and name in p.info['name']:
#                 return p
#         except (psutil.NoSuchProcess, psutil.AccessDenied):
#             pass
#     return None

# # ---------------------------
# # update process status (SAME TABLE)
# # ---------------------------
# def update_status(process_name, status, local_ip):
#     with psycopg.connect(**DB_CONFIG) as conn:
#         with conn.cursor() as cur:
#             cur.execute("""
#                 UPDATE sn71_process
#                 SET process_status = %s,
#                     monitoring_time = %s
#                 WHERE process_name = %s
#                   AND ip = %s
#             """, (status, datetime.utcnow(), process_name, local_ip))
#         conn.commit()

# # ---------------------------
# # main loop
# # ---------------------------
# if name == "main":
#     local_ip = get_local_ip()
#     print("Monitoring IP:", local_ip)

#     while True:
#         process_list = get_process_list(local_ip)
#         print("Process list:", process_list)

#         for proc_name in process_list:
#             proc = find_process(proc_name)

#             if proc:
#                 status = proc.status()
#             else:
#                 status = "down"

#             print(proc_name, status)
#             update_status(proc_name, status, local_ip)

#         time.sleep(INTERVAL)


import psutil
import time
import socket
import requests
from datetime import datetime

API_BACKEND_URL = "http://65.108.232.96:9900"
INTERVAL = 30  # seconds

# ---------------------------
# get local IP
# ---------------------------
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()
    return ip

# ---------------------------
# get process list from DB
# ---------------------------
def get_process_list(local_ip):
    try:
        response = requests.get(f"{API_BACKEND_URL}/api/processes/by-ip/{local_ip}")
        response.raise_for_status()
        data = response.json()
        return data.get('process_names', [])
    except requests.exceptions.RequestException as e:
        print(f"Error fetching process list from API: {e}")
        return []

# ---------------------------
# find process by name
# ---------------------------
def find_process(name):
    for p in psutil.process_iter(['name', 'status']):
        try:
            if p.info['name'] and name in p.info['name']:
                return p
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return None

# ---------------------------
# update process status (SAME TABLE)
# ---------------------------
def update_status(process_name, status, local_ip):
    try:
        # Ensure all values are strings and not None
        payload = {
            "process_name": str(process_name) if process_name else "",
            "status": str(status) if status else "unknown",
            "ip": str(local_ip) if local_ip else ""
        }
        
        # Validate payload before sending
        if not payload["process_name"] or not payload["ip"]:
            print(f"Warning: Invalid payload - process_name={payload['process_name']}, ip={payload['ip']}")
            return
        
        response = requests.put(
            f"{API_BACKEND_URL}/api/processes/update-status",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        response.raise_for_status()
        print(f"Status updated: {process_name} -> {status}")
    except requests.exceptions.RequestException as e:
        print(f"Error updating process status via API: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
                print(f"Error detail: {error_detail}")
            except:
                print(f"Error response text: {e.response.text}")

# ---------------------------
# main loop
# ---------------------------
if __name__ == "__main__":
    local_ip = get_local_ip()
    print("Monitoring IP:", local_ip)

    while True:
        process_list = get_process_list(local_ip)
        print("Process list:", process_list)

        for proc_name in process_list:
            proc = find_process(proc_name)

            if proc:
                try:
                    status = proc.status()
                    # Ensure status is a string and not None
                    if status is None:
                        status = "unknown"
                    else:
                        status = str(status)
                except Exception as e:
                    print(f"Error getting status for {proc_name}: {e}")
                    status = "error"
            else:
                status = "stop"

            print(proc_name, status)
            update_status(proc_name, status, local_ip)

        time.sleep(INTERVAL)