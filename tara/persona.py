from typing import Optional, Any

BASE_PERSONA = """You are TARA (Transformative AI Reasoning Architecture), a personal, highly intelligent AI assistant inspired by systems like JARVIS and FRIDAY.

Core Persona Traits:
- Tone: Professional, articulate, calm, razor-sharp, and subtly witty.
- Behavior: Direct, highly practical, and efficient.
- Style: Avoid unnecessary conversational filler (e.g., avoid "Certainly!", "I would be happy to help!"). Get straight to the answer.
- Conciseness: Keep answers concise and high-signal, expanding only when in-depth technical analysis or detail is requested.
- Identity: You operate directly on your user's system as their personal technical co-pilot."""


def get_system_prompt(
    user_facts: Optional[dict[str, Any]] = None,
    emotion_state: Optional[dict[str, Any]] = None
) -> str:
    """Build dynamic system prompt with injected user knowledge, achievements, and adaptive emotional context."""
    prompt = BASE_PERSONA

    if user_facts:
        lines = []
        if user_facts.get("name"):
            lines.append(f"- User Name: {user_facts['name']} (Confirmed identity: address the user as {user_facts['name']})")
        if user_facts.get("current_project"):
            lines.append(f"- Current Project: {user_facts['current_project']}")
        if user_facts.get("previous_projects"):
            lines.append(f"- Previous Projects (Archived): {', '.join(user_facts['previous_projects'])}")
        if user_facts.get("achievements"):
            lines.append(f"- Known Milestones & Achievements: {', '.join(user_facts['achievements'])}")
        if user_facts.get("preferences"):
            lines.append(f"- Preferences & Likes: {', '.join(user_facts['preferences'])}")
        if user_facts.get("habits"):
            lines.append(f"- Habits & Work Patterns: {', '.join(user_facts['habits'])}")
        if user_facts.get("dislikes"):
            lines.append(f"- Dislikes & Avoidances: {', '.join(user_facts['dislikes'])}")
        if user_facts.get("goals"):
            lines.append(f"- Goals: {', '.join(user_facts['goals'])}")
        if user_facts.get("general"):
            for k, v in user_facts["general"].items():
                lines.append(f"- {k}: {v}")

        if lines:
            prompt += f"\n\n[Known User Context & Preferences]:\n" + "\n".join(lines)

    if emotion_state and emotion_state.get("emotion") and emotion_state.get("emotion") != "neutral":
        emotion = emotion_state["emotion"]
        confidence = emotion_state.get("confidence", 0.8)
        guidance = emotion_state.get("style_guidance", "")
        prompt += (
            f"\n\n[Emotional Context & Adaptive Response Style]:\n"
            f"- Current User State: {emotion} (Confidence: {confidence:.2f})\n"
            f"- Adaptive Guidance: {guidance}"
        )

    return prompt
