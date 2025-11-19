#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AgentX subagent usando a API de alto nível (Opção 1 - CORRIGIDA v4)

CORREÇÃO FINAL: O log de erro confirmou:
1. Scalars são criados vazios (agent.DisplayString()) e depois configurados (.oid, .Value, .mode).
2. A Tabela é criada com argumentos posicionais no construtor:
   agent.Table(oidstr, indexes, columns)
"""

import os
import time
import json
import logging
import sys

try:
    import netsnmpagent
except Exception as e:
    print("Erro: não foi possível importar netsnmpagent (use --system-site-packages and install python3-netsnmpagent).", e)
    raise

# ---------- CONFIG ----------
STATUS_FILE = os.path.join(os.path.dirname(__file__), "status.json")
MASTER_SOCKET = "/var/agentx/master"
AGENT_NAME = "AutoDiscoveryAgent"
BASE_OID = "1.3.6.1.3.9999"   # conforme sua MIB
POLL = 1.0  # loop interval (s)
# ----------------------------

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
log = logging.getLogger("autodiscovery-agent")

def load_status():
    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # default structure if file missing or broken
        return {
            "control": {"targetNetwork": "auto", "silentMode": 0, "forceScan": 0},
            "status": {"nextScanInSeconds": 0, "scansPerformedTotal": 0, "lastScanDeviceCount": 0},
            "devices": []
        }

def save_status(data):
    try:
        tmp = STATUS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, STATUS_FILE)
    except Exception as e:
        log.error("Falha ao salvar status.json: %s", e)

# ---------- helper to make OID strings used by high-level API ----------
def oid_str(suffix):
    return BASE_OID + suffix

# ---------- create agent + scalars + table ----------
log.info("Creating netsnmpagent (AgentX subagent)...")
try:
    agent = netsnmpagent.netsnmpAgent(
        AgentName=AGENT_NAME,
        MasterSocket=MASTER_SOCKET,
        MIBFiles=[]
    )
except Exception as e:
    log.error("Falha ao inicializar o netsnmpAgent. O socket %s está acessível?", MASTER_SOCKET)
    log.error(e)
    sys.exit(1)


# Load initial JSON
status = load_status()

log.info("Registrando Scalars...")
# Control group (read-write)
try:
    # Esta é a API CORRETA para scalars (confirmado pelo log)
    targetNetwork = agent.DisplayString()
    targetNetwork.oid = oid_str(".1.1.1.0")
    targetNetwork.Value = str(status.get("control", {}).get("targetNetwork", "auto"))
    targetNetwork.mode = "readwrite"

    forceScanTrigger = agent.Integer32()
    forceScanTrigger.oid = oid_str(".1.1.2.0")
    forceScanTrigger.Value = int(status.get("control", {}).get("forceScan", 0))
    forceScanTrigger.mode = "readwrite"

    silentMode = agent.Integer32()
    silentMode.oid = oid_str(".1.1.3.0")
    silentMode.Value = int(status.get("control", {}).get("silentMode", 0))
    silentMode.mode = "readwrite"

    # Status group (read-only)
    nextScanInSeconds = agent.Unsigned32()
    nextScanInSeconds.oid = oid_str(".1.2.1.0")
    nextScanInSeconds.Value = int(status.get("status", {}).get("nextScanInSeconds", 0))

    scansPerformedTotal = agent.Counter32()
    scansPerformedTotal.oid = oid_str(".1.2.2.0")
    scansPerformedTotal.Value = int(status.get("status", {}).get("scansPerformedTotal", 0))
    
    lastScanDeviceCount = agent.Unsigned32()
    lastScanDeviceCount.oid = oid_str(".1.2.3.0")
    lastScanDeviceCount.Value = int(status.get("status", {}).get("lastScanDeviceCount", 0))
    
except Exception as e:
    log.error("Erro fatal ao criar scalars: %s", e)
    sys.exit(1)


log.info("Registrando Tabela...")
# Device table
try:
    # CORREÇÃO FINAL: O erro de log exige 3 argumentos POSICIONAIS
    device_table = agent.Table(
        oid_str(".1.3"),        # 1. 'oidstr'
        [agent.Integer32()],    # 2. 'indexes'
        [                       # 3. 'columns'
            agent.IpAddress(),
            agent.DisplayString(),
            agent.Integer32(),
            agent.DisplayString(),
            agent.DisplayString(),
            agent.TimeTicks(),
            agent.Integer32(),
            agent.DisplayString(),
            agent.DisplayString()
        ]
    )
    USE_TABLE_HIGH = True
    log.info("Device table object created using high-level API.")

except Exception as e:
    log.warning("Falha ao criar device_table (Esta era a última tentativa): %s", e)
    device_table = None
    USE_TABLE_HIGH = False


# helper to repopulate table from status["devices"]
def refresh_table():
    if device_table is None:
        log.debug("Pulando refresh_table, pois a tabela não foi criada.")
        return
    try:
        device_table.clear()
    except Exception:
        pass

    devices = status.get("devices", [])
    for idx, dev in enumerate(devices, start=1):
        ip = dev.get("ip", "0.0.0.0")
        mac = dev.get("mac", "")
        st_str = dev.get("status", "unresponsive")
        st = 1 if st_str == "online" else 2
        vendor = dev.get("producer", dev.get("manufacturer", ""))
        role = dev.get("role", "")
        firstSeen = 0 # TimeTicks
        ttl_raw = dev.get("ttl")
        ttl = int(ttl_raw) if isinstance(ttl_raw, (int, float)) else 0
        snmpName = dev.get("snmp_name", "")
        openPorts = ",".join(str(p) for p in dev.get("open_ports", []) if p is not None)

        try:
            device_table.addRow(idx, [ip, mac, st, vendor, role, firstSeen, ttl, snmpName, openPorts])
        except Exception as e:
            log.debug(f"Falha ao adicionar linha {idx} na table (ignorada): {e}")

# initial populate
refresh_table()

log.info("AgentX subagent initialized. Entering main loop.")
log.info("Master socket: %s", MASTER_SOCKET)

# Keep last-known control scalars to detect changes (for persistence) 
last_target = targetNetwork.Value
last_force = int(forceScanTrigger.Value)
last_silent = int(silentMode.Value)

try:
    agent.start()
    log.info("Agent.start() chamado.")
except Exception as e:
    log.warning("agent.start() falhou: %s. Entrando no loop manual.", e)

# main loop: sync JSON -> scalars/table and scalars->JSON on SETs
try:
    while True:
        # process SNMP requests quickly
        try:
            agent.check_and_process(0) 
        except Exception:
            pass

        # reload status file (other processes may write it)
        new_status = load_status()
        
        # Se o status mudou no disco, atualize tudo
        if new_status != status:
            status = new_status
            log.debug("status.json mudou no disco, recarregando scalars e tabela.")
            refresh_table() # Atualiza a tabela agora que o status mudou

        # --- sync JSON -> exposed scalars (if changed externally) ---
        j_target = str(new_status.get("control", {}).get("targetNetwork", "auto"))
        if j_target != targetNetwork.Value:
            targetNetwork.Value = j_target
            last_target = j_target

        j_force = int(new_status.get("control", {}).get("forceScan", 0) or 0)
        if j_force != int(forceScanTrigger.Value):
            forceScanTrigger.Value = j_force
            last_force = j_force

        j_silent = int(new_status.get("control", {}).get("silentMode", 0) or 0)
        if j_silent != int(silentMode.Value):
            silentMode.Value = j_silent
            last_silent = j_silent

        # --- detect SETs (scalars changed via SNMP) and persist to status.json ---
        cur_target = targetNetwork.Value
        cur_force = int(forceScanTrigger.Value)
        cur_silent = int(silentMode.Value)

        wrote = False
        # targetNetwork SET?
        if cur_target != last_target:
            log.info("Detected SET targetNetwork -> %s", cur_target)
            new_status.setdefault("control", {})["targetNetwork"] = str(cur_target)
            last_target = str(cur_target)
            wrote = True

        # silentMode SET?
        if cur_silent != last_silent:
            log.info("Detected SET silentMode -> %d", cur_silent)
            new_status.setdefault("control", {})["silentMode"] = int(cur_silent)
            last_silent = int(cur_silent)
            wrote = True

        # forceScanTrigger: if SNMP client wrote 1, act as trigger and reset to 0
        if cur_force != last_force:
            log.info("Detected SET forceScanTrigger -> %d", cur_force)
            if int(cur_force) == 1:
                new_status.setdefault("control", {})["forceScan"] = 1
                forceScanTrigger.Value = 0
                log.info("ForceScan triggered; reset scalar to 0.")
                last_force = 0 # O valor agora é 0
            else:
                new_status.setdefault("control", {})["forceScan"] = int(cur_force)
                last_force = int(cur_force)
            wrote = True

        if wrote:
            save_status(new_status)
            status = new_status # Atualiza o status em memória

        # --- sync status -> exposed read-only scalars (from JSON) ---
        try:
            ns = status.get("status", {})
            nextScanInSeconds.Value = int(ns.get("nextScanInSeconds", 0) or 0)
            scansPerformedTotal.Value = int(ns.get("scansPerformedTotal", 0) or 0)
            lastScanDeviceCount.Value = int(ns.get("lastScanDeviceCount", 0) or 0)
        except Exception:
            pass

        # small sleep to avoid busy loop
        time.sleep(POLL)
        
except KeyboardInterrupt:
    log.info("Interrupted by user. Exiting.")
    sys.exit(0)
except Exception as e:
    log.error(f"Erro fatal no loop principal: {e}")
    sys.exit(1)
finally:
    log.info("Desligando o agente...")
    agent.shutdown()