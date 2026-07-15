from dataclasses import dataclass
from typing import Any, Callable, Optional, Sequence

import streamlit as st


@dataclass
class EntitySelection:
    mode: str
    selected_record: Optional[Any] = None

    @property
    def is_existing(self) -> bool:
        return (
            self.mode == "Existing"
            and self.selected_record is not None
        )

    @property
    def is_new(self) -> bool:
        return self.mode == "Create New"

    @property
    def is_none(self) -> bool:
        return self.mode in {
            "None",
            "Open",
        }


def entity_selector(
    *,
    label: str,
    records: Sequence[Any],
    format_func: Callable[[Any], str],
    key: str,
    allow_new: bool = True,
    allow_none: bool = True,
    none_label: str = "None",
    new_label: str = "Create New",
) -> EntitySelection:
    modes = ["Existing"]

    if allow_new:
        modes.append(new_label)

    if allow_none:
        modes.append(none_label)

    mode = st.radio(
        f"{label} source",
        modes,
        horizontal=True,
        key=f"{key}_mode",
    )

    if mode == "Existing":
        if not records:
            st.info(
                f"No existing {label.lower()} records are available."
            )

            return EntitySelection(
                mode="Existing",
                selected_record=None,
            )

        selected_record = st.selectbox(
            label,
            options=list(records),
            format_func=format_func,
            key=f"{key}_existing",
        )

        return EntitySelection(
            mode="Existing",
            selected_record=selected_record,
        )

    if mode == new_label:
        return EntitySelection(mode="Create New")

    return EntitySelection(mode="None")