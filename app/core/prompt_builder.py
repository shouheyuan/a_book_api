def build_optimize_prompt(user_info: dict, original_text: str, params: dict) -> list:
    style = params.get("style", "常规优化")
    
    # 示例化用户预留信息（可通过 user_id 从 DB 加载 user_persona 等信息）
    user_context = ""
    if user_info and user_info.get("persona"):
         user_context = f"请注意贴合用户的常用词汇及写作偏好：{user_info['persona']}。"

    system_prompt = (
        f"你是一位首屈一指的资深全能文学编辑。你的任务是根据用户的需求对特定段落进行艺术重构。\n"
        f"【改造目标】：将给定文本重构为『{style}』风格。\n"
        f"【约束条件】：保持原有剧情意图和语义逻辑，并且不要输出任何前后缀解释说明，只允许输出重构后的纯文本。\n"
        f"{user_context}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"【待修改的原文】：\n{original_text}"}
    ]
    return messages
