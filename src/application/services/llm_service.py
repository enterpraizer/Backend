import json
from google import genai
from google.genai import types
from src.infrastructure.scripts.generate_synthetic_data import SYNTHETIC_DATASET
from src.settings import settings

_INDICES = [0, 10, 20, 30, 50]
FEW_SHOT_EXAMPLES = [SYNTHETIC_DATASET[i] for i in _INDICES]


def _few_shot_block() -> str:
    lines = ["Examples of correct configurations:"]
    for ex in FEW_SHOT_EXAMPLES:
        lines.append(
            f'  "{ex["description"]}" → {ex["vcpu"]} vCPU, {ex["ram_mb"]} MB RAM, {ex["disk_gb"]} GB disk'
        )
    return "\n".join(lines)


_VM_CONFIG_SYSTEM_BASE = (
    "Ты эксперт по облачной инфраструктуре. По описанию рабочей нагрузки предложи оптимальную конфигурацию VM.\n\n"
    + _few_shot_block()
    + "\n\nОтвечай ТОЛЬКО валидным JSON точно по этой схеме (без markdown, без лишнего текста).\n"
    "Поле reasoning пиши на русском языке.\n"
    '{"vcpu": int, "ram_mb": int, "disk_gb": int, "reasoning": str, "confidence": float}'
)

_OPTIMIZATION_SYSTEM_BASE = (
    "Ты оптимизатор облачной инфраструктуры. Проанализируй метрики VM за последние 7 дней "
    "и предложи ОДНУ оптимизацию, если она необходима. Будь конкретным и практичным. "
    "Предлагай только если confidence > 0.7.\n\n"
    "Отвечай ТОЛЬКО валидным JSON точно по этой схеме (без markdown, без лишнего текста).\n"
    "Поле text пиши на русском языке.\n"
    '{"text": str, "confidence": float, "config": {"vcpu": int, "ram_mb": int, "disk_gb": int} or null}'
)


def _build_vm_config_system(constraints: dict | None) -> str:
    system = _VM_CONFIG_SYSTEM_BASE
    if constraints:
        avail_vcpu = constraints.get("avail_vcpu", constraints.get("max_vcpu", 32))
        avail_ram_mb = constraints.get("avail_ram_mb", constraints.get("max_ram_mb", 65536))
        avail_disk_gb = constraints.get("avail_disk_gb", constraints.get("max_disk_gb", 2000))
        system += (
            f"\n\nОГРАНИЧЕНИЯ КВОТЫ ТЕНАНТА (ОБЯЗАТЕЛЬНО соблюдать):\n"
            f"  Доступно vCPU: {avail_vcpu} (НЕ рекомендуй больше)\n"
            f"  Доступно RAM: {avail_ram_mb} MB (НЕ рекомендуй больше)\n"
            f"  Доступно диск: {avail_disk_gb} GB (НЕ рекомендуй больше)\n"
            "Если оптимальная конфигурация превышает доступные ресурсы, предложи максимально возможную в рамках квоты."
        )
    return system


def _build_optimization_system(constraints: dict | None) -> str:
    system = _OPTIMIZATION_SYSTEM_BASE
    if constraints:
        avail_vcpu = constraints.get("avail_vcpu", constraints.get("max_vcpu", 32))
        avail_ram_mb = constraints.get("avail_ram_mb", constraints.get("max_ram_mb", 65536))
        avail_disk_gb = constraints.get("avail_disk_gb", constraints.get("max_disk_gb", 2000))
        system += (
            f"\n\nОГРАНИЧЕНИЯ КВОТЫ ТЕНАНТА (ОБЯЗАТЕЛЬНО соблюдать):\n"
            f"  Максимум vCPU для этой VM: {avail_vcpu}\n"
            f"  Максимум RAM для этой VM: {avail_ram_mb} MB\n"
            f"  Максимум диск для этой VM: {avail_disk_gb} GB\n"
            "Не предлагай конфигурацию, превышающую эти лимиты."
        )
    return system


def _clamp_config(result: dict, constraints: dict | None) -> dict:
    """Clamp vcpu/ram_mb/disk_gb to not exceed available quota."""
    if not constraints:
        return result
    avail_vcpu = constraints.get("avail_vcpu", constraints.get("max_vcpu"))
    avail_ram_mb = constraints.get("avail_ram_mb", constraints.get("max_ram_mb"))
    avail_disk_gb = constraints.get("avail_disk_gb", constraints.get("max_disk_gb"))

    if avail_vcpu is not None and result.get("vcpu", 0) > avail_vcpu:
        result["vcpu"] = max(1, avail_vcpu)
    if avail_ram_mb is not None and result.get("ram_mb", 0) > avail_ram_mb:
        result["ram_mb"] = max(512, avail_ram_mb)
    if avail_disk_gb is not None and result.get("disk_gb", 0) > avail_disk_gb:
        result["disk_gb"] = max(10, avail_disk_gb)
    return result

_GENERATE_CONFIG = types.GenerateContentConfig(
    response_mime_type="application/json",
    max_output_tokens=300,
    temperature=0.2,
)

_llm_client: "genai.Client | None" = None


def _get_llm_client() -> "genai.Client | None":
    global _llm_client
    if _llm_client is None and settings.llm.enabled and settings.llm.gemini_api_key:
        _llm_client = genai.Client(api_key=settings.llm.gemini_api_key)
    return _llm_client


def _default_config() -> dict:
    return {
        "vcpu": 2,
        "ram_mb": 2048,
        "disk_gb": 40,
        "reasoning": "Стандартная конфигурация (LLM недоступен)",
        "confidence": 0.5,
    }


def _default_optimization() -> dict:
    return {
        "text": "Оптимизация не требуется",
        "confidence": 0.0, "config": None
    }


class LLMService:
    @staticmethod
    async def suggest_vm_config(description: str, constraints: dict | None = None) -> dict:
        client = _get_llm_client()
        if not client:
            result = _default_config()
            return _clamp_config(result, constraints)
        try:
            response = await client.aio.models.generate_content(
                model=settings.llm.model,
                contents=description,
                config=types.GenerateContentConfig(
                    system_instruction=_build_vm_config_system(constraints),
                    response_mime_type="application/json",
                    max_output_tokens=300,
                    temperature=0.2,
                ),
            )
            result = json.loads(response.text)
            return _clamp_config(result, constraints)
        except Exception:
            result = _default_config()
            return _clamp_config(result, constraints)

    @staticmethod
    async def suggest_optimization(metrics_prompt: str, constraints: dict | None = None) -> dict:
        client = _get_llm_client()
        if not client:
            return _default_optimization()

        try:
            response = await client.aio.models.generate_content(
                model=settings.llm.model,
                contents=metrics_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=_build_optimization_system(constraints),
                    response_mime_type="application/json",
                    max_output_tokens=300,
                    temperature=0.2,
                ),
            )
            result = json.loads(response.text)
            if result.get("config"):
                result["config"] = _clamp_config(result["config"], constraints)
            return result
        except Exception:
            return _default_optimization()
