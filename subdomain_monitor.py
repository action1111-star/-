import os
import re
import json
import subprocess
import sys
import requests

# --- الإعدادات ---
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCOPE_FILE = os.path.join(BASE_DIR, "data", "scope.txt")          # قايمة الـ wildcards الخام (بترفعها انت)
DB_FILE = os.path.join(BASE_DIR, "data", "subdomains_db.json")     # الحالة المحفوظة بين كل تشغيلة
SUBFINDER_CONCURRENCY = "50"                                        # عدد الدومينات اللي بتتفحص بالتوازي
SUBFINDER_TIMEOUT = "30"                                            # timeout بالثواني لكل مصدر


def extract_domains(scope_file_path):
    """
    يفلتر ملف الـ scope الخام ويطلع منه دومينات صحيحة بس.
    بيشيل: الـ paths (اللي فيها /)، الأسطر اللي مش شكلها دومين
    (زي "Firmware", "Mobile apps owned by...")، والـ wildcard المزدوج زي *.*
    """
    domain_pattern = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9\-\.]*[a-zA-Z0-9])?\.[a-zA-Z]{2,}$")
    domains = set()

    with open(scope_file_path, "r", encoding="utf-8", errors="ignore") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue

            # شيل بادئات wildcard شائعة: *.، **.، *-
            cleaned = line
            cleaned = re.sub(r"^\*+\)?\.?", "", cleaned)   # *. أو *) أو **.
            cleaned = re.sub(r"^https?://", "", cleaned)
            cleaned = cleaned.split("/")[0]                 # شيل أي path بعد الدومين
            cleaned = cleaned.strip().strip("*").strip()

            if not cleaned or "*" in cleaned or " " in cleaned:
                continue
            if "." not in cleaned:
                continue
            if not domain_pattern.match(cleaned):
                continue

            domains.add(cleaned.lower())

    return sorted(domains)


def run_subfinder(domains):
    """
    يشغل subfinder على قايمة دومينات ويرجع dict: {domain: set(subdomains)}
    """
    if not domains:
        return {}

    input_file = "/tmp/domains_input.txt"
    output_file = "/tmp/subfinder_output.txt"

    with open(input_file, "w") as f:
        f.write("\n".join(domains))

    cmd = [
        "subfinder",
        "-dL", input_file,
        "-silent",
        "-t", SUBFINDER_CONCURRENCY,
        "-timeout", SUBFINDER_TIMEOUT,
        "-o", output_file,
    ]

    print(f"[*] Running subfinder on {len(domains)} domains...")
    try:
        subprocess.run(cmd, check=True, timeout=60 * 60 * 5)  # حد أقصى 5 ساعات أمان
    except subprocess.TimeoutExpired:
        print("[-] subfinder timed out, using partial results.")
    except subprocess.CalledProcessError as e:
        print(f"[-] subfinder exited with error: {e}")

    results = {}
    if os.path.exists(output_file):
        with open(output_file, "r") as f:
            for line in f:
                sub = line.strip().lower()
                if not sub:
                    continue
                # استنتاج الدومين الأساسي بمطابقة اللاحقة
                for d in domains:
                    if sub == d or sub.endswith("." + d):
                        results.setdefault(d, set()).add(sub)
                        break

    return results


def send_discord_alert(domain, new_subs):
    """إرسال إشعار لديسكورد عن sub-domains جديدة"""
    chunk_size = 20
    subs_list = sorted(new_subs)
    for i in range(0, len(subs_list), chunk_size):
        chunk = subs_list[i:i + chunk_size]
        description = "\n".join(f"`{s}`" for s in chunk)
        payload = {
            "embeds": [{
                "title": "🛰️ New Subdomains Detected!",
                "color": 15158332,
                "fields": [
                    {"name": "🎯 Root Domain", "value": f"`{domain}`", "inline": False},
                    {"name": f"🆕 New Subdomains ({len(chunk)})", "value": description[:1024], "inline": False},
                ],
                "footer": {"text": "Subdomain Radar Automation"}
            }]
        }
        try:
            r = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
            r.raise_for_status()
        except Exception as e:
            print(f"[-] Discord sending failed for {domain}: {e}")


def main():
    if not DISCORD_WEBHOOK_URL:
        print("[-] DISCORD_WEBHOOK_URL env var is missing. Set it as a GitHub Secret.")
        sys.exit(1)

    if not os.path.exists(SCOPE_FILE):
        print(f"[-] Scope file not found at {SCOPE_FILE}. Upload your scope list there.")
        sys.exit(1)

    domains = extract_domains(SCOPE_FILE)
    print(f"[+] Extracted {len(domains)} valid domains from scope file.")

    # تحميل الداتابيز القديمة
    old_db = {}
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            try:
                old_db = json.load(f)
            except json.JSONDecodeError:
                pass

    is_first_run = len(old_db) == 0

    new_results = run_subfinder(domains)

    new_db = {}
    total_new = 0

    for domain in domains:
        current_subs = sorted(new_results.get(domain, set()))
        new_db[domain] = current_subs

        if not is_first_run and current_subs:
            old_subs = set(old_db.get(domain, []))
            diff = [s for s in current_subs if s not in old_subs]

            if diff:
                print(f"[+] Found {len(diff)} new subdomains for {domain}!")
                send_discord_alert(domain, diff)
                total_new += len(diff)

    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    with open(DB_FILE, "w") as f:
        json.dump(new_db, f, indent=2)

    if is_first_run:
        print(f"[+] First run complete. Baseline saved for {len(new_db)} domains. No alerts sent.")
    else:
        print(f"[+] Sync complete. {total_new} new subdomains found across {len(new_db)} domains.")


if __name__ == "__main__":
    main()
