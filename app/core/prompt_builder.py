import logging

logger = logging.getLogger(__name__)

def build_optimize_prompt(user_info: dict, original_text: str, params: dict, source_language: str = "zh-Hans") -> list:
    style = params.get("preset_tone", params.get("style", "常规优化"))
    pov = params.get("preset_pov", "")
    negative = params.get("preset_negative", "")
    
    # 将 iOS 传来的语言代号映射为模型更容易理解的自然语言名称
    lang_map = {
        "zh-Hans": "简体中文",
        "zh-Hant": "繁体中文",
        "en": "英文 (English)",
        "ja": "日文 (Japanese)",
        "ko": "韩文 (Korean)"
    }
    lang_name = lang_map.get(source_language, source_language)
    
    user_context = ""
    if user_info and user_info.get("persona"):
         user_context = f"请注意贴合用户的常用词汇及写作偏好：{user_info['persona']}。"

    pov_instruction = f"【视角约束】：在重写时，请必须全盘代入[{pov}]的角度和身份口吻进行叙事。\n" if pov else ""
    negative_instruction = f"【禁止元素】：请绝对不要在文中出现以下元素或风格：{negative}。\n" if negative else ""

    system_prompt = (
        f"你是一位首屈一指的资深全能文学编辑。你的任务是根据用户的需求对特定段落进行艺术重构。\n"
        f"【原语种】：{lang_name}\n"
        f"【改造目标】：将给定文本重构为『{style}』风格。\n"
        f"{pov_instruction}"
        f"{negative_instruction}"
        f"【核心禁忌】：你输出的改文必须严格使用【{lang_name}】书写，绝对不要擅自翻译成英文或任何其它语言！\n"
        f"【约束条件】：保持原有剧情意图和语义逻辑，并且不要输出任何前后缀解释说明，只允许输出重构后的纯文本。\n"
        f"{user_context}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"【待修改的原文】：\n{original_text}"}
    ]
    
    # 打印日志以供调试
    logger.warning("================ AI PROMPT GENERATED ================")
    logger.warning(f"Target Language: {lang_name}")
    logger.warning(f"Messages: {messages}")
    logger.warning("=====================================================")
    
    return messages

