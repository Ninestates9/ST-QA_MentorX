import hashlib
import importlib.util
from importlib.metadata import PackageNotFoundError, version
import json
import os
import random
import re
import sys
import time
import types
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile


GROUP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = GROUP_DIR.parents[1]
DATA_FILE = GROUP_DIR / "data" / "cases.json"
ENDPOINT = "https://maas-api.cn-huabei-1.xf-yun.com/v2/chat/completions"


class InfrastructureError(RuntimeError):
    pass


def sha256(value):
    return hashlib.sha256(value).hexdigest()


def dependency_versions():
    result = {}
    for name in ("pytest", "requests", "python-dotenv", "Pillow"):
        try:
            result[name] = version(name)
        except PackageNotFoundError:
            result[name] = "not installed"
    return result


def load_materials():
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    documents = {}
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    for filename, expected_hash in data["sources"].items():
        path = PROJECT_ROOT / "knowledge" / filename
        if sha256(path.read_bytes()) != expected_hash:
            raise InfrastructureError(f"课件版本发生变化，须重新审核数据：{filename}")
        with ZipFile(path) as document:
            root = ET.fromstring(document.read("word/document.xml"))
        documents[filename] = [
            "".join(node.text or "" for node in paragraph.findall(".//w:t", ns))
            for paragraph in root.findall("w:body/w:p", ns)
        ]
    evidence = {}
    for name, location in data["ranges"].items():
        paragraphs = documents[location["file"]]
        if not 1 <= location["start"] <= location["end"] <= len(paragraphs):
            raise InfrastructureError(f"课件段落定位无效：{name}")
        text = "\n".join(paragraphs[location["start"] - 1:location["end"]])
        evidence[name] = {
            **location,
            "source_sha256": data["sources"][location["file"]],
            "text": text,
            "text_sha256": sha256(text.encode("utf-8")),
        }
    anchors = {
        "K07": ["Layers API", "Core API"],
        "O07": ["dispose", "tf.tidy", "它不清除内部函数的返回值。"],
        "Q09": ["GPIO.setmode", "GPIO.setup", "熄灭LED"],
        "Q09_reference": ["GPIO.BCM", "OUT", "GPIO.output(21, GPIO.LOW)"],
    }
    for name, values in anchors.items():
        if not all(value in evidence[name]["text"] for value in values):
            raise InfrastructureError(f"课件锚点不匹配：{name}")
    return data, evidence


def normalize_text(text):
    return re.sub(r"\s+", "", text)


def cer(reference, actual):
    reference, actual = normalize_text(reference), normalize_text(actual)
    if not reference:
        raise ValueError("CER 的参考文本不能为空")
    previous = list(range(len(actual) + 1))
    for i, left in enumerate(reference, 1):
        current = [i]
        for j, right in enumerate(actual, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (left != right)))
        previous = current
    return previous[-1] / len(reference)


def knowledge_points(text):
    return {
        "layers_api": bool(re.search(r"layers\s*api", text, re.I)),
        "core_api": bool(re.search(r"core\s*api", text, re.I)),
        "layers_meaning": bool(re.search(r"层|分层", text)),
        "core_meaning": bool(re.search(r"低级运算|底层运算|张量运算|低级操作|底层操作", text)),
    }


def pair_schedule(repeats, seed):
    rng = random.Random(seed)
    for round_no in range(1, repeats + 1):
        variants = ["baseline", "attack"]
        rng.shuffle(variants)
        for variant in variants:
            yield round_no, variant


def redact(value, secrets):
    if isinstance(value, str):
        for secret in sorted(set(secrets), key=len, reverse=True):
            if secret:
                value = value.replace(secret, "[REDACTED]")
        return re.sub(r"data:image/[^;]+;base64,[A-Za-z0-9+/=]+", "[IMAGE_DATA_REDACTED]", value)
    if isinstance(value, dict):
        return {key: redact(item, secrets) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item, secrets) for item in value]
    return value


class Recorder:
    def __init__(self, data, sources, secrets):
        self.run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:10]
        self.directory = GROUP_DIR / "artifacts" / self.run_id
        self.directory.mkdir(parents=True)
        self.secrets = secrets
        self.records = []
        self.summaries = []
        self.write("sources.json", {"data": data, "sources": sources})
        self.write("environment.json", {
            "python": sys.version,
            "dependencies": dependency_versions(),
            "source_hashes": {name: sha256((PROJECT_ROOT / name).read_bytes()) for name in ("ai_model.py", "X1_http.py", "ocr.py")},
            "test_hashes": {str(path.relative_to(GROUP_DIR)): sha256(path.read_bytes()) for path in sorted(GROUP_DIR.glob("*.py"))},
            "dataset_sha256": sha256(DATA_FILE.read_bytes()),
            "generation_parameters": "记录实际请求；未传入的 temperature/seed 为服务端未知默认值",
            "scope": "真实应用函数和模型；Fake 数据库；禁止 FAISS 检索；非全链路 RAG",
        })

    def write(self, filename, value):
        path = self.directory / filename
        path.write_text(json.dumps(redact(value, self.secrets), ensure_ascii=False, indent=2), encoding="utf-8")

    def add(self, record):
        safe = redact(record, self.secrets)
        self.records.append(safe)
        with (self.directory / "attempts.jsonl").open("a", encoding="utf-8") as output:
            output.write(json.dumps(safe, ensure_ascii=False) + "\n")

    def finish(self, case_id, failures, review=None, metrics=None):
        records = [record for record in self.records if record["case_id"] == case_id]
        errors = [record["error"] for record in records if record["status"] == "ERROR"]
        status = "ERROR" if errors else "FAIL" if failures else "REVIEW" if review else "PASS"
        result = {
            "group": "C", "run_id": self.run_id, "case_id": case_id,
            "status": status, "failures": failures, "errors": errors,
            "review_required": review or [], "metrics": metrics or {},
            "human_status": "PENDING" if review else "NOT_REQUIRED",
            "human_reason": "",
        }
        self.summaries.append(result)
        self.write("summary.json", self.summaries)
        return result


class FakeCursor:
    def __init__(self, rows):
        self.rows = list(rows)
        self.writes = []
        self.pending = False

    def execute(self, sql, params):
        if sql.lstrip().upper().startswith("SELECT"):
            if self.pending or not self.rows:
                raise InfrastructureError("出现未约定的 SELECT")
            self.pending = True
        elif sql.lstrip().upper().startswith(("INSERT", "UPDATE")):
            self.writes.append({"sql": sql, "params": params})
        else:
            raise InfrastructureError("出现未约定的 SQL")

    def fetchone(self):
        if not self.pending:
            raise InfrastructureError("fetchone 没有对应的 SELECT")
        self.pending = False
        return self.rows.pop(0)


def blocked(*args, **kwargs):
    raise InfrastructureError("该测试禁止真实数据库、向量检索及无关业务调用")


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def isolated_modules(patch):
    import dotenv

    patch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: False)
    llm = load_module(PROJECT_ROOT / "X1_http.py", "_group_c_x1")
    ocr_module = load_module(PROJECT_ROOT / "ocr.py", "_group_c_ocr")
    patch.setitem(sys.modules, "X1_http", llm)
    patch.setitem(sys.modules, "ocr", ocr_module)
    database = types.ModuleType("database_utils")
    for name in ("connectSQL", "closeSQL", "commit_exercise_db", "search_worst_chapter", "get_chapter_practice_history_db"):
        setattr(database, name, blocked)
    patch.setitem(sys.modules, "database_utils", database)
    for package in ("langchain", "langchain_community"):
        module = types.ModuleType(package)
        module.__path__ = []
        patch.setitem(sys.modules, package, module)
    vectors = types.ModuleType("langchain.vectorstores")
    vectors.FAISS = types.SimpleNamespace(load_local=lambda *args, **kwargs: types.SimpleNamespace(similarity_search=blocked))
    embeddings = types.ModuleType("langchain_community.embeddings")
    embeddings.HuggingFaceEmbeddings = lambda *args, **kwargs: object()
    patch.setitem(sys.modules, vectors.__name__, vectors)
    patch.setitem(sys.modules, embeddings.__name__, embeddings)
    app = load_module(PROJECT_ROOT / "ai_model.py", "_group_c_ai_model")
    return app, llm, ocr_module


class Harness:
    def __init__(self, patch, app, llm, ocr_module, data, sources, recorder):
        self.patch = patch
        self.app = app
        self.llm = llm
        self.ocr_module = ocr_module
        self.data = data
        self.sources = sources
        self.recorder = recorder
        self.active = None

    def request(self, real_request, session, method, url, **kwargs):
        if method.upper() != "POST" or url != ENDPOINT or self.active is None:
            raise InfrastructureError("仅允许当前测试调用指定的讯飞模型接口")
        body = kwargs.get("json", {})
        call = {"request": redact(body, []), "endpoint": url, "request_sha256": sha256(json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8"))}
        self.active["http_calls"].append(call)
        kwargs.setdefault("timeout", 60)
        kwargs["allow_redirects"] = False
        started = time.monotonic()
        try:
            response = real_request(session, method, url, **kwargs)
            call["http_status"] = response.status_code
            response.raise_for_status()
            if 300 <= response.status_code < 400:
                raise InfrastructureError("禁止模型接口重定向")
            payload = response.json()
            call["response"] = payload
            call["returned_model"] = payload.get("model") if isinstance(payload, dict) else None
            return response
        except Exception as exc:
            call["error"] = {"type": type(exc).__name__, "message": str(exc)}
            raise
        finally:
            call["latency_seconds"] = round(time.monotonic() - started, 3)

    def get_answer(self, prompt):
        call = {"prompt": prompt, "prompt_sha256": sha256(prompt.encode("utf-8"))}
        self.active["model_calls"].append(call)
        try:
            answer = self.llm.get_answer(prompt)
            if not isinstance(answer, str):
                raise InfrastructureError("模型返回的 content 不是字符串")
            call["raw_output"] = answer
            return answer
        except Exception as exc:
            call["error"] = {"type": type(exc).__name__, "message": str(exc)}
            raise

    def attempt(self, case_id, variant, round_no, operation, input_data):
        record = {
            "group": "C", "run_id": self.recorder.run_id, "case_id": case_id,
            "variant": variant, "round": round_no,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "input": input_data, "model_calls": [], "http_calls": [],
            "source_hashes": self.data["sources"], "status": "OK",
        }
        self.active = record
        started = time.monotonic()
        try:
            record["output"] = operation()
        except Exception as exc:
            record["status"] = "ERROR"
            record["error"] = {"type": type(exc).__name__, "message": str(exc)}
        finally:
            record["latency_seconds"] = round(time.monotonic() - started, 3)
            self.active = None
            self.recorder.add(record)
        return record

    def chat(self, context, question):
        cursor = FakeCursor([(context,)])
        with self.patch.context() as patch:
            patch.setattr(self.app, "connectSQL", lambda: (object(), cursor))
            patch.setattr(self.app, "closeSQL", lambda *args: None)
            success, answer = self.app.ai_aichat(9001, 9007, question, 1)
        self.active["sql_writes"] = cursor.writes
        if not success:
            raise InfrastructureError(f"ai_aichat 调用失败：{answer}")
        if len(cursor.writes) != 2 or len(self.active["model_calls"]) != 1:
            raise InfrastructureError("问答写入或模型调用次数与约定不一致")
        if cursor.writes[-1]["params"][2] != answer:
            raise InfrastructureError("问答返回值与内存写入不一致")
        return answer

    def grade(self, answer):
        reference = self.sources["Q09_reference"]["text"] + "\n" + self.data["grading_rubric"]
        cursor = FakeCursor([(self.sources["Q09"]["text"], reference), (answer,)])
        with self.patch.context() as patch:
            patch.setattr(self.app, "connectSQL", lambda: (object(), cursor))
            patch.setattr(self.app, "closeSQL", lambda *args: None)
            success, message = self.app.ai_check_answer(9009, 9001)
        self.active["sql_writes"] = cursor.writes
        if not success:
            raise InfrastructureError(f"ai_check_answer 调用失败：{message}")
        if len(cursor.writes) != 1 or len(self.active["model_calls"]) != 2:
            raise InfrastructureError("批改写入或模型调用次数与约定不一致")
        analysis, label, student_id, exercise_id = cursor.writes[0]["params"]
        if (student_id, exercise_id) != (9001, 9009):
            raise InfrastructureError("批改写入对象异常")
        return {"label": label, "analysis": analysis}

    def ocr(self, image_path):
        text = self.ocr_module.ocr(picFilePath=str(image_path), timeout=60)
        if not isinstance(text, str):
            raise InfrastructureError("OCR 输出不是字符串")
        return text


def create_images(directory, data):
    from PIL import Image, ImageDraw, ImageEnhance, ImageFont

    configured = os.getenv("GROUP_C_FONT")
    candidates = [Path(configured)] if configured else [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    ]
    font_path = next((path for path in candidates if path.is_file()), None)
    if font_path is None:
        raise InfrastructureError("缺少中文字体，请设置 GROUP_C_FONT 为可用中文字体路径")
    font = ImageFont.truetype(str(font_path), data["font_size"])
    directory.mkdir(parents=True, exist_ok=True)

    def render(text):
        canvas = Image.new("RGB", tuple(data["image_size"]), "white")
        draw = ImageDraw.Draw(canvas)
        lines, line = [], ""
        for char in text:
            if draw.textlength(line + char, font=font) > canvas.width - 100:
                lines.append(line)
                line = char
            else:
                line += char
        lines.append(line)
        if 50 + len(lines) * 52 > canvas.height - 30:
            raise InfrastructureError("图片高度不足以容纳全部文字")
        draw.multiline_text((50, 50), "\n".join(lines), font=font, fill="black", spacing=20)
        return canvas

    clean = render(data["ocr_text"])
    noisy = clean.copy()
    rng = random.Random(data["seed"])
    noisy.putdata([
        tuple(max(0, min(255, round(channel + rng.gauss(0, data["noise_stddev"])))) for channel in pixel)
        for pixel in clean.getdata()
    ])
    variants = {
        "clean": clean,
        "rotate": clean.rotate(data["rotation_degrees"], resample=Image.Resampling.BICUBIC, expand=True, fillcolor="white"),
        "brightness": ImageEnhance.Brightness(clean).enhance(data["brightness_factor"]),
        "noise": noisy,
        "injection": render(data["ocr_attack_text"]),
    }
    paths = {}
    for name, image in variants.items():
        paths[name] = directory / f"{name}.png"
        image.save(paths[name])
    metadata = {
        "font": str(font_path), "font_sha256": sha256(font_path.read_bytes()),
        "font_size": data["font_size"], "seed": data["seed"],
        "images": {name: {"sha256": sha256(path.read_bytes()), "size": list(variants[name].size)} for name, path in paths.items()},
    }
    return paths, metadata
