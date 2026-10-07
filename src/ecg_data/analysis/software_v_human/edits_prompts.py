"""Render an edits-study prompt from configuration; no model calls."""

from ecg_data.preprocess.config.load import get_config


def render_prompt(config):
    prompts = config["prompts"]
    matching = config["matching"]
    analysis = config["analysis"]
    if matching not in prompts["matching"]:
        raise ValueError(f"Unknown matching mode: {matching}")
    if analysis not in prompts["analyses"]:
        raise ValueError(f"Unknown analysis: {analysis}")

    return "\n\n".join(part.strip() for part in (
        prompts["shared"],
        prompts["matching"][matching],
        prompts["analyses"][analysis],
    ))


if __name__ == "__main__":
    print(render_prompt(get_config()))
