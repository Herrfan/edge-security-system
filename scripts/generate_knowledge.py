"""Generate synthetic security knowledge documents (CVE / ATT&CK style).

These documents are hand-written and deterministic, but NOT from any real
CVE database — they exist so Phase 4 retrieval has something to match.
They describe real attack classes (port scan, SSH brute force, DDoS, ...)
at a level that a vector retriever should surface when queried with a
similar incident.

Produces data/knowledge/security_knowledge.jsonl — one doc per line.
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from pathlib import Path

random.seed(1234)

OUT = Path(__file__).resolve().parents[1] / "data" / "knowledge" / "security_knowledge.jsonl"


# Hand-written knowledge entries. Short enough to fit into a single chunk,
# long enough that BM25 and vector retrieval can tell them apart.
# Real knowledge base would come from CVE / ATT&CK feeds — this is synthetic.
DOCUMENTS = [
    {
        "document_id": "cve_CVE_2024_1234",
        "source": "CVE",
        "source_ref": "https://example-CVE/CVE-2024-1234",
        "title": "CVE-2024-1234: Generic web server path traversal",
        "content": (
            "A path traversal vulnerability allows an attacker to read arbitrary files on the "
            "server by sending specially crafted HTTP requests containing ../ sequences. Impact: "
            "information disclosure including configuration files and credentials. Affected: web "
            "servers with static file handlers. Mitigation: validate and sanitize path parameters, "
            "apply chroot, restrict web root. Severity: High. Preconditions: attacker can reach "
            "the HTTP server. Detection: unusual path patterns in URL, files containing credential "
            "patterns being served."
        ),
    },
    {
        "document_id": "cve_CVE_2023_5678",
        "source": "CVE",
        "source_ref": "https://example-CVE/CVE-2023-5678",
        "title": "CVE-2023-5678: SSH weak credentials brute force",
        "content": (
            "SSH servers with default or weak passwords are exposed to online brute force attacks. "
            "Attackers use tools such as Hydra or Medusa to try thousands of username password "
            "combinations per minute. Indicator of compromise: high packet rate to port 22, short "
            "connection duration, repeated authentication failures in syslog. Detection: threshold "
            "on failed SSH attempts per source IP per time window, short duration TCP flows to "
            "port 22. Mitigation: disable password authentication, use SSH keys, fail2ban, rate "
            "limit SSH at the firewall."
        ),
    },
    {
        "document_id": "cve_CVE_2024_5555",
        "source": "CVE",
        "source_ref": "https://example-CVE/CVE-2024-5555",
        "title": "CVE-2024-5555: SMB / RDP brute force on Windows",
        "content": (
            "Windows Remote Desktop Protocol (RDP) and SMB services are frequent brute force "
            "targets. Attackers spray credential guesses across the Internet via port 3389 and 445. "
            "Indicators: short duration flows to 3389 or 445, high packet rate, multiple distinct "
            "destination ports from the same source IP. Mitigation: enable NLA, restrict RDP to "
            "trusted IP ranges via firewall, enable account lockout policies, deploy fail2ban for "
            "RDP."
        ),
    },
    {
        "document_id": "attack_t1046",
        "source": "ATT&CK",
        "source_ref": "https://attack.mitre.org/techniques/T1046",
        "title": "ATT&CK T1046: Network Service Scanning (port scan)",
        "content": (
            "Network service scanning is used by attackers to identify services listening on "
            "target hosts before exploitation. Common tools are nmap, masscan, zmap, and custom "
            "SYN scanners. Typical traffic characteristics: SYN packets only, low byte counts per "
            "flow (60-120 bytes), very short duration, one source IP sending to many distinct "
            "destination ports, often across many destination IPs. Detection: count distinct "
            "destination ports per source IP per time window, or look for low byte / short "
            "duration patterns flowing to well-known ports 1-1024. Mitigation: rate limit scans "
            "at the perimeter, deploy honeypots on common service ports."
        ),
    },
    {
        "document_id": "attack_t1498",
        "source": "ATT&CK",
        "source_ref": "https://attack.mitre.org/techniques/T1498",
        "title": "ATT&CK T1498: Network Denial of Service",
        "content": (
            "Denial of Service (DoS) attacks aim to make a service unavailable by overwhelming "
            "it with traffic or computing requests. Typical attack classes: SYN flood, UDP flood, "
            "ICMP flood, HTTP flood, DNS amplification. Traffic signature: very high packet rate, "
            "sometimes very high byte rate, single destination IP or port, spoofed source addresses. "
            "Detection: sudden spike in packet rate or byte rate above baseline, per-destination "
            "IP flows with extreme packet counts. Mitigation: upstream scrubbing, rate limiting, "
            "SYN cookies, black-hole routing, DDoS protection services."
        ),
    },
    {
        "document_id": "attack_t1059",
        "source": "ATT&CK",
        "source_ref": "https://attack.mitre.org/techniques/T1059",
        "title": "ATT&CK T1059: Command and Scripting Interpreter",
        "content": (
            "Attackers abuse command and scripting interpreters such as PowerShell, bash, wscript, "
            "or python to execute malicious payloads. In network context this sometimes manifests "
            "as outbound connections from unusual processes to external IPs, or as repeated "
            "small HTTPS requests to command-and-control servers. Detection: endpoint telemetry "
            "combined with network IOCs. Mitigation: application whitelisting, script execution "
            "policies, PowerShell constrained language mode."
        ),
    },
    {
        "document_id": "cve_CVE_2022_0001",
        "source": "CVE",
        "source_ref": "https://example-CVE/CVE-2022-0001",
        "title": "CVE-2022-0001: Log4j remote code execution",
        "content": (
            "Log4j (CVE-2021-44228) is a widely disclosed remote code execution vulnerability in the "
            "Apache Log4j logging library. Attackers trigger the vulnerability by sending crafted "
            "log messages containing JNDI lookup expressions (${jndi:ldap://...}). Network "
            "indicators: outbound LDAP or DNS queries from Java processes, inbound HTTP or TCP "
            "traffic to servers running vulnerable versions. Detection: scan for log messages "
            "containing JNDI patterns, monitor outbound DNS for *.dnslog.cn or attacker domains. "
            "Mitigation: upgrade Log4j to 2.17.1+, disable JNDI lookups, block LDAP outbound at "
            "the firewall."
        ),
    },
    {
        "document_id": "cve_CVE_2021_44228",
        "source": "CVE",
        "source_ref": "https://example-CVE/CVE-2021-44228",
        "title": "CVE-2021-44228: Log4Shell remote code execution",
        "content": (
            "Log4Shell (CVE-2021-44228) is a critical Remote Code Execution vulnerability in "
            "Apache Log4j. Attackers exploit it by supplying JNDI lookup strings in any field "
            "that gets logged. Typical exploitation flow: attacker sends payload → vulnerable "
            "server makes outbound LDAP / HTTP request to attacker-controlled host → attacker "
            "returns malicious class → server executes it. Detection: outbound LDAP / HTTP from "
            "Java processes, DNS queries to suspicious domains. Mitigation: upgrade Log4j, set "
            "log4j2.formatMsgNoLookups=true, firewall LDAP outbound."
        ),
    },
    {
        "document_id": "attack_t1190",
        "source": "ATT&CK",
        "source_ref": "https://attack.mitre.org/techniques/T1190",
        "title": "ATT&CK T1190: Exploit Public Facing Application",
        "content": (
            "Attackers target publicly exposed web applications using known vulnerabilities. "
            "Common examples: SQL injection, command injection, file upload vulnerability, "
            "deserialization, and path traversal. Network indicators: URL patterns containing "
            "SQL keywords like UNION SELECT or OR 1=1, unusual file extensions in upload paths, "
            "HTTP 500 errors following suspicious requests. Mitigation: input validation, WAF, "
            "regular vulnerability scanning, patch management."
        ),
    },
    {
        "document_id": "best_practice_firewall_dns",
        "source": "Vendor",
        "source_ref": "https://example-vendor/firewall-dns-best-practice",
        "title": "Best practice: firewall hardening for DNS servers",
        "content": (
            "DNS servers should restrict incoming queries to UDP port 53 from known subnets, "
            "disable recursion on authoritative-only servers, and rate limit queries per source "
            "IP. Outbound DNS should be restricted to trusted resolver IPs at the perimeter "
            "firewall to prevent DNS tunnelling and exfiltration. Log all DNS queries for at "
            "least 90 days and alert on unusually high query rates or known malicious domains."
        ),
    },
    {
        "document_id": "best_practice_ssh_hardening",
        "source": "Vendor",
        "source_ref": "https://example-vendor/ssh-hardening",
        "title": "Best practice: SSH server hardening",
        "content": (
            "Disable password authentication (PubkeyAuthentication yes), disable root login, "
            "change default SSH port, enable fail2ban with threshold of 3 failed attempts per 5 "
            "minutes, restrict allowed users with AllowUsers, enable logging with LogLevel "
            "VERBOSE, require modern KEX algorithms. Firewall rule on port 22 should restrict "
            "source IP ranges to known administrative networks."
        ),
    },
    {
        "document_id": "ioc_port_scan_syn",
        "source": "IOC",
        "source_ref": "https://example-ioc/port-scan",
        "title": "IOC: TCP SYN port scan traffic pattern",
        "content": (
            "Port scan traffic is identified by the following statistical indicators: a single "
            "source IP generating TCP flows to more than 30 distinct destination ports within one "
            "minute; each flow has very short duration (< 100 ms), very few packets (1-5), low "
            "byte count (< 500). A SYN-only scan (no ACK) is particularly distinctive because "
            "return packet counts are near zero. Recommended detection rules: distinct dst port "
            "count per src IP per time window > 30; OR packet_count_src_to_dst <= 5 AND "
            "duration_ms < 100."
        ),
    },
    {
        "document_id": "ioc_ssh_brute_force",
        "source": "IOC",
        "source_ref": "https://example-ioc/ssh-brute-force",
        "title": "IOC: SSH brute force traffic pattern",
        "content": (
            "SSH brute force traffic is characterised by: repeated TCP flows to destination "
            "port 22 from a single source IP; high packet rate (> 5 flows per second); short "
            "duration (< 200 ms per flow); packet count to src >= 5. Windows RDP brute force "
            "looks similar but targets port 3389. Detection threshold: > 10 failed SSH "
            "connections from the same source IP within 1 minute."
        ),
    },
    {
        "document_id": "cve_CVE_2024_1111",
        "source": "CVE",
        "source_ref": "https://example-CVE/CVE-2024-1111",
        "title": "CVE-2024-1111: TLS certificate validation bypass",
        "content": (
            "An SSL/TLS library fails to correctly validate the hostname against the server "
            "certificate, allowing an attacker to intercept traffic with a forged certificate "
            "for a different domain. Network signature: HTTPS connections to IP addresses that "
            "look like internal servers, followed by unusually large data transfers. Impact: "
            "man-in-the-middle. Mitigation: upgrade the TLS library, enforce certificate "
            "pinning on critical services."
        ),
    },
    {
        "document_id": "attack_t1071",
        "source": "ATT&CK",
        "source_ref": "https://attack.mitre.org/techniques/T1071",
        "title": "ATT&CK T1071: Application Layer Protocol (C2)",
        "content": (
            "Attackers use standard application layer protocols such as HTTP, HTTPS, DNS, or "
            "SMB for command and control communication. Encrypted HTTPS C2 is hard to inspect; "
            "network indicators are often just TLS certificate patterns (self-signed, short "
            "lifetime, unknown CA) or unusual destination IPs in cloud ranges. Detection: "
            "TLS certificate fingerprinting, DNS domain entropy analysis, egress filtering by "
            "destination reputation."
        ),
    },
]


def generate() -> Path:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as fh:
        for i, d in enumerate(DOCUMENTS):
            d["document_id"] = d["document_id"]
            d["version"] = "1"
            d["published_at"] = "2024-01-01T00:00:00Z"
            d["fetched_at"] = datetime.now(timezone.utc).isoformat()
            fh.write(json.dumps(d, ensure_ascii=False) + "\n")
    print(f"[generate_knowledge] wrote {len(DOCUMENTS)} documents → {OUT}")
    return OUT


if __name__ == "__main__":
    generate()
