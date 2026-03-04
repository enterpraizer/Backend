import anthropic

from src.infrastructure.scripts.generate_synthetic_data import SYNTHETIC_DATASET
from src.settings import settings

VM_CONFIG_TOOL = {
    "name": "suggest_vm_config",
    "description": "Suggest optimal VM configuration for the described workload",
    "input_schema": {
        "type": "object",
        "properties": {
            "vcpu": {"type": "integer", "minimum": 1, "maximum": 32},
            "ram_mb": {"type": "integer", "minimum": 512, "maximum": 65536},
            "disk_gb": {"type": "integer", "minimum": 10, "maximum": 500},
            "reasoning": {"type": "string"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": ["vcpu", "ram_mb", "disk_gb", "reasoning", "confidence"],
    },
}

# Pick 5 diverse examples spread across the 6 categories (one per category, skip game servers)
_INDICES = [0, 10, 20, 30, 50]  # Web, DB, ML, CI/CD, Microservices
FEW_SHOT_EXAMPLES = [SYNTHETIC_DATASET[i] for i in _INDICES]


def _build_system_prompt(examples: list[dict]) -> str:
    lines = [
        "You are a cloud infrastructure expert. Given a workload description, "
        "suggest the optimal VM configuration using the suggest_vm_config tool.\n",
        "Examples of good configurations:",
    ]
    for ex in examples:
        lines.append(
            f'  "{ex["description"]}" → {ex["vcpu"]} vCPU, {ex["ram_mb"]} MB RAM, {ex["disk_gb"]} GB disk'
        )
    lines.append("\nAlways use the tool to return structured output.")
    return "\n".join(lines)


def _parse_tool_response(response) -> dict:
    for block in response.content:
        if block.type == "tool_use" and block.name == "suggest_vm_config":
            return block.input
    return _default_config()


def _default_config() -> dict:
    return {
        "vcpu": 2,
        "ram_mb": 2048,
        "disk_gb": 40,
        "reasoning": "Default configuration (LLM unavailable)",
        "confidence": 0.5,
    }


class LLMService:
    async def suggest_vm_config(self, description: str) -> dict:
        """
        Calls Anthropic Claude with few-shot examples to suggest VM config.
        Returns: {vcpu, ram_mb, disk_gb, reasoning, confidence}
        Falls back to default config if API unavailable or disabled.
        """
        if not settings.llm.enabled or not settings.llm.anthropic_api_key:
            return _default_config()

        try:
            client = anthropic.AsyncAnthropic(api_key=settings.llm.anthropic_api_key)
            response = await client.messages.create(
                model=settings.llm.model,
                max_tokens=300,
                tools=[VM_CONFIG_TOOL],
                tool_choice={"type": "tool", "name": "suggest_vm_config"},
                system=_build_system_prompt(FEW_SHOT_EXAMPLES),
                messages=[{"role": "user", "content": description}],
            )
            return _parse_tool_response(response)
        except Exception:
            return _default_config()
