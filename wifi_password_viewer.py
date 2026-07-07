import subprocess

profiles = subprocess.check_output("netsh wlan show profiles",shell=True).decode()


names = [line.split(":")[1].strip() for line in profiles.split("\n") if "All User Profiles" in line]

for i, n in enumerate(names, 1):
    print(f"[i]")