import re
from typing import List
from pydantic import BaseModel, Field


class UniversalState(BaseModel):
    """
    UniversalState schema acting as the 'Hub' for AI agent context preservation.
    """
    architecture_stack: List[str] = Field(default_factory=list)
    completed_features: List[str] = Field(default_factory=list)
    work_in_progress: str = Field(default="None")
    known_issues: List[str] = Field(default_factory=list)
    next_move: str = Field(default="None")

    def to_markdown(self) -> str:
        """
        Converts the UniversalState into a cleanly formatted markdown string.
        Matches the standard VIBE-SYNC format.
        """
        arch_str = ", ".join(self.architecture_stack) if self.architecture_stack else "[To be filled]"
        comp_str = "\n".join([f"- {feat}" for feat in self.completed_features]) if self.completed_features else "None"
        issues_str = "\n".join([f"- {issue}" for issue in self.known_issues]) if self.known_issues else "None yet."

        md = f"""# 🧠 VIBE-SYNC PROJECT CONTEXT

## 🏗 Architecture & Stack
{arch_str}

## 🚦 Current Progress
- **Completed Features:** {comp_str}
- **Work in Progress:** {self.work_in_progress}

## 🐛 Known Issues / Technical Debt
{issues_str}

## ➡️ The Next Move
{self.next_move}
"""
        return md

    @classmethod
    def from_markdown(cls, md_string: str) -> "UniversalState":
        """
        A classmethod that parses a VIBE_CONTEXT.md formatted string back 
        into a UniversalState object.
        """
        state = cls()

        # Extract Architecture & Stack
        arch_match = re.search(r"## 🏗 Architecture & Stack\n(.*?)\n\n##", md_string, re.S)
        if arch_match:
            arch_text = arch_match.group(1).strip()
            if arch_text and arch_text != "[To be filled]":
                state.architecture_stack = [item.strip() for item in arch_text.split(",")]

        # Extract Completed Features
        comp_match = re.search(r"- \*\*Completed Features:\*\* (.*?)\n- \*\*Work in Progress:\*\*", md_string)
        if comp_match:
            comp_text = comp_match.group(1).strip()
            if comp_text != "None":
                # Handle single line if not bulleted or multi-line bullet
                if "\n" in comp_text:
                    state.completed_features = [f.strip("- ").strip() for f in comp_text.split("\n") if f.strip()]
                else:
                    state.completed_features = [f.strip() for f in comp_text.split(",") if f.strip()]

        # Extract Work in Progress
        wip_match = re.search(r"- \*\*Work in Progress:\*\* (.*?)\n\n##", md_string)
        if wip_match:
            state.work_in_progress = wip_match.group(1).strip()

        # Extract Known Issues
        issues_match = re.search(r"## 🐛 Known Issues / Technical Debt\n(.*?)\n\n##", md_string, re.S)
        if issues_match:
            issues_text = issues_match.group(1).strip()
            if issues_text and issues_text != "None yet.":
                state.known_issues = [i.strip("- ").strip() for i in issues_text.split("\n") if i.strip()]

        # Extract Next Move
        next_match = re.search(r"## ➡️ The Next Move\n(.*?)$", md_string, re.S)
        if next_match:
            state.next_move = next_match.group(1).strip()

        return state
