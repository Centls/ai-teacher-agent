# -*- coding: utf-8 -*-
"""Test audio transcription API"""
import httpx

file_path = r"d:\心宇未来\ai-teacher-nexus\data\uploads\4762c5a5-c2b4-4485-9fea-eccc816c12b9_20260110_122618_1_.m4a"

try:
    r = httpx.post(
        "http://127.0.0.1:8010/transcribe",
        json={"file_path": file_path},
        timeout=300
    )
    result = r.json()

    if result.get("success"):
        print("=== 转录成功 ===")
        print(f"语言: {result.get('metadata', {}).get('language', 'unknown')}")
        print(f"文本长度: {len(result.get('text', ''))} 字符")
        print("\n=== 转录内容 ===")
        print(result.get("text", ""))
    else:
        print(f"转录失败: {result.get('error')}")
except Exception as e:
    print(f"请求失败: {e}")