"""
Process Manager for QMD MCP Server

功能：
1. 查找所有qmd server进程
2. 从进程命令行提取端口
3. 停止所有server进程（调试用）
"""
import psutil
import re
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


def find_server_processes() -> List[psutil.Process]:
    """
    Find all 'qmd server' processes.
    
    Returns:
        List of running qmd server processes
    """
    server_procs = []
    
    try:
        for proc in psutil.process_iter(['name', 'cmdline', 'create_time']):
            try:
                cmdline = proc.info.get('cmdline', [])
                if not cmdline:
                    continue
                
                cmdline_str = ' '.join(cmdline)
                
                # 检测是否是qmd server命令
                is_qmd = 'qmd' in cmdline_str
                is_server = 'server' in cmdline_str
                
                if is_qmd and is_server:
                    server_procs.append(proc)
            
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    
    return server_procs


def get_server_port_from_process(proc: psutil.Process) -> int | Optional[int]:
    """
    Extract port from server process command line.
    
    Args:
        proc: Process object
    
    Returns:
        Port number if found, None otherwise
    """
    try:
        cmdline = ' '.join(proc.info.get('cmdline', []))
        
        # 查找--port参数
        match = re.search(r'--port\s+(\d+)', cmdline)
        if match:
            return int(match.group(1))
        
        # 默认端口
        return DEFAULT_PORT
    
    except Exception:
        logger.warning(f"Failed to extract port from process: {e}")
        return None


def kill_server_processes():
    """
    Attempt to kill all qmd server processes.
    
    Warning: Use only for debugging/testing!
    """
    procs = find_server_processes()
    
    for proc in procs:
        try:
            logger.info(f"Killing server process PID {proc.pid}")
            proc.terminate()
        except psutil.NoSuchProcess:
            pass
