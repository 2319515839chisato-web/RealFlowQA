# run_structure.py
"""
Batch call gpt-5.4 to parse flowchart images into Figure2StructuralText,
and save the outputs by chart_id to structure/chart_xxx_structure.json.

The final saved structure JSON retains only the following top-level fields:
- chart_id
- title
- lanes
- nodes
- edges
"""
import json
import re
import time
import sys
from pathlib import Path

import pandas as pd


# =========================
# Project root directory setup
# =========================
ROOT_DIR = Path(__file__).resolve().parent

sys.path.insert(0, str(ROOT_DIR))

from prompts import build_structure_prompt
from clients import get_model_client


# =========================
# Model configuration
# =========================
MODEL_NAME = "gpt-5.4"

API_KEY = ""

BASE_URL = "https://api.aigc.bar/v1"


# =========================
# Path configuration
# =========================
QUESTIONS_FILE = str(ROOT_DIR / "data" / "questions.xlsx")
IMAGES_DIR = str(ROOT_DIR / "data" / "images")
OUTPUT_DIR = str(ROOT_DIR / "structure")


# =========================
# Runtime configuration
# =========================
MAX_CHARTS = None
OVERWRITE = False
MAX_RETRIES = 5
SLEEP_SECONDS = 5


def safe_value(v):
    if pd.isna(v):
        return ""
    return str(v).strip()


def load_questions(file_path: str) -> pd.DataFrame:
    if file_path.endswith(".xlsx"):
        return pd.read_excel(file_path)
    elif file_path.endswith(".csv"):
        return pd.read_csv(file_path)
    else:
        raise ValueError("不支持的文件格式: %s" % file_path)


def find_image_path(chart_id: str, images_dir: str) -> Path:
    candidate_exts = [
        ".png", ".jpg", ".jpeg", ".webp",
        ".PNG", ".JPG", ".JPEG", ".WEBP"
    ]

    for ext in candidate_exts:
        p = Path(images_dir) / ("%s%s" % (chart_id, ext))
        if p.exists():
            return p

    for p in Path(images_dir).iterdir():
        if p.is_file() and chart_id in p.stem and p.suffix in candidate_exts:
            return p

    raise FileNotFoundError("找不到图片文件: %s" % chart_id)


def get_unique_chart_ids(df: pd.DataFrame) -> list:
    if "chart_id" not in df.columns:
        raise ValueError("questions.xlsx 中缺少 chart_id 列")

    chart_ids = []
    seen = set()

    for v in df["chart_id"].dropna().tolist():
        chart_id = safe_value(v)
        if chart_id and chart_id not in seen:
            chart_ids.append(chart_id)
            seen.add(chart_id)

    return chart_ids


def clean_json_text(text: str) -> str:
    if text is None:
        return ""

    text = str(text).strip()

    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    return text.strip()


def extract_json_from_response(text: str) -> dict:
    raw = clean_json_text(text)

    try:
        return json.loads(raw)
    except Exception:
        pass

    start = raw.find("{")
    end = raw.rfind("}")

    if start != -1 and end != -1 and end > start:
        candidate = raw[start:end + 1]
        try:
            return json.loads(candidate)
        except Exception:
            pass

    raise ValueError("模型输出不是可解析 JSON")


def normalize_structure(data: dict, chart_id: str) -> dict:
    """
    Normalize the structure returned by the model.

    The final output retains only the following top-level fields:
    - chart_id
    - title
    - lanes
    - nodes
    - edges
    """
    if not isinstance(data, dict):
        data = {}

    lanes = data.get("lanes", [])
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])

    if not isinstance(lanes, list):
        lanes = []
    if not isinstance(nodes, list):
        nodes = []
    if not isinstance(edges, list):
        edges = []

    clean_lanes = []
    for lane in lanes:
        if not isinstance(lane, dict):
            continue

        clean_lanes.append({
            "lane_id": str(lane.get("lane_id", "")).strip(),
            "name": str(lane.get("name", "")).strip(),
            "description": str(lane.get("description", "")).strip()
        })

    clean_nodes = []
    for node in nodes:
        if not isinstance(node, dict):
            continue

        text = str(node.get("text", "")).strip()
        full_label = str(node.get("full_label", "")).strip()

        if not full_label:
            full_label = text

        clean_nodes.append({
            "node_id": str(node.get("node_id", "")).strip(),
            "text": text,
            "full_label": full_label,
            "lane_id": str(node.get("lane_id", "")).strip(),
            "responsible": str(node.get("responsible", "")).strip()
        })

    clean_edges = []
    for edge in edges:
        if not isinstance(edge, dict):
            continue

        clean_edges.append({
            "edge_id": str(edge.get("edge_id", "")).strip(),
            "from": str(edge.get("from", "")).strip(),
            "to": str(edge.get("to", "")).strip(),
            "condition": str(edge.get("condition", "")).strip(),
            "edge_type": str(edge.get("edge_type", "normal")).strip() or "normal",
            "description": str(edge.get("description", "")).strip()
        })

    normalized = {
        "chart_id": chart_id,
        "title": str(data.get("title", "")).strip(),
        "lanes": clean_lanes,
        "nodes": clean_nodes,
        "edges": clean_edges
    }

    return normalized


def save_structure(output_dir: str, chart_id: str, structure_data: dict, raw_response: str):
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    json_file = Path(output_dir) / ("%s_structure.json" % chart_id)
    raw_file = Path(output_dir) / ("%s_structure_raw.txt" % chart_id)

    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(structure_data, f, ensure_ascii=False, indent=2)

    with open(raw_file, "w", encoding="utf-8") as f:
        f.write(str(raw_response))


def save_raw_error(output_dir: str, chart_id: str, raw_response: str, error_message: str = ""):
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    raw_file = Path(output_dir) / ("%s_structure_raw.txt" % chart_id)
    error_file = Path(output_dir) / ("%s_structure_error.txt" % chart_id)

    with open(raw_file, "w", encoding="utf-8") as f:
        f.write(str(raw_response))

    with open(error_file, "w", encoding="utf-8") as f:
        f.write("模型输出无法解析为 JSON。\n")
        if error_message:
            f.write("\n错误信息：\n")
            f.write(str(error_message))


def main():
    if not API_KEY or API_KEY.startswith("请填写"):
        raise ValueError("请先在 run_structure.py 中填写 API_KEY")

    df = load_questions(QUESTIONS_FILE)
    chart_ids = get_unique_chart_ids(df)

    if MAX_CHARTS is not None:
        chart_ids = chart_ids[:MAX_CHARTS]

    total_charts = len(chart_ids)

    client = get_model_client(MODEL_NAME, api_key=API_KEY, base_url=BASE_URL)

    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    print("开始批量生成 Figure2StructuralText")
    print("模型：%s" % MODEL_NAME)
    print("流程图数量：%d" % total_charts)
    print("问题文件：%s" % QUESTIONS_FILE)
    print("图片目录：%s" % IMAGES_DIR)
    print("输出目录：%s" % OUTPUT_DIR)
    print("最终保存字段：chart_id, title, lanes, nodes, edges")

    success_count = 0
    fail_count = 0
    skip_count = 0

    for idx, chart_id in enumerate(chart_ids, start=1):
        chart_id = str(chart_id)

        json_file = Path(OUTPUT_DIR) / ("%s_structure.json" % chart_id)

        if json_file.exists() and not OVERWRITE:
            print("\n[%d/%d] %s 已存在，跳过" % (idx, total_charts, chart_id))
            skip_count += 1
            continue

        print("\n[%d/%d] 解析 %s" % (idx, total_charts, chart_id))

        try:
            image_path = find_image_path(chart_id, IMAGES_DIR)
        except Exception as e:
            print("  找不到图片：%s" % str(e))
            fail_count += 1
            continue

        prompt = build_structure_prompt(chart_id)

        success = False
        last_response = ""
        last_error = ""

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                print("  第 %d 次请求：%s" % (attempt, image_path))

                response = client.query(str(image_path), prompt)
                last_response = response

                structure_data = extract_json_from_response(response)
                structure_data = normalize_structure(structure_data, chart_id)

                save_structure(OUTPUT_DIR, chart_id, structure_data, response)

                print("  成功保存：%s_structure.json" % chart_id)

                success_count += 1
                success = True
                break

            except Exception as e:
                last_error = str(e)
                print("  第 %d 次失败：%s" % (attempt, last_error))

                if attempt < MAX_RETRIES:
                    print("  等待 %.1f 秒后重试..." % SLEEP_SECONDS)
                    time.sleep(SLEEP_SECONDS)

        if not success:
            print("  最终失败：%s" % chart_id)

            if last_response:
                save_raw_error(OUTPUT_DIR, chart_id, last_response, last_error)

            fail_count += 1

        time.sleep(SLEEP_SECONDS)

    print("\n处理完成")
    print("成功：%d" % success_count)
    print("失败：%d" % fail_count)
    print("跳过：%d" % skip_count)
    print("结果目录：%s" % OUTPUT_DIR)


if __name__ == "__main__":
    main()