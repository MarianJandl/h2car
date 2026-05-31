from textual.widgets import Static

NUMERIC_KEYS = ["Vbat", "Iout", "Pout", "Vfc", "Pfc", "Tfc"]


class StatsDashboard(Static):
    def __init__(self):
        super().__init__()
        self.stats = {
            key: {"min": float("inf"), "max": float("-inf"), "avg": 0, "count": 0, "sum": 0}
            for key in NUMERIC_KEYS
        }
        self.update_stats(None, None, None)

    def _fmt(self, key, field, suffix, decimals=2):
        """Format one stat field, or '--' when no samples have been seen yet."""
        if self.stats[key]["count"] == 0:
            return f"-- {suffix}"
        return f"{self.stats[key][field]:.{decimals}f}{suffix}"

    def update_stats(self, data, napomenutiF, napomenutiV):
        if data is not None:
            for key in NUMERIC_KEYS:
                if key in data:
                    try:
                        value = float(data[key])
                    except (ValueError, TypeError):
                        continue
                    stat = self.stats[key]
                    stat["min"] = min(stat["min"], value)
                    stat["max"] = max(stat["max"], value)
                    stat["count"] += 1
                    stat["sum"] += value
                    stat["avg"] = stat["sum"] / stat["count"]

        def row(label, key, suffix):
            return (
                f"{label:<5} Min: {self._fmt(key, 'min', suffix)} | "
                f"Max: {self._fmt(key, 'max', suffix)} | "
                f"Avg: {self._fmt(key, 'avg', suffix)}"
            )

        self.update(
            f"{row('Vbat', 'Vbat', 'V')}\n"
            f"{row('Iout', 'Iout', 'A')}\n"
            f"{row('Pout', 'Pout', 'W')}\n"
            f"{row('Vfc', 'Vfc', 'V')}\n"
            f"{row('Pfc', 'Pfc', 'W')}\n"
            f"{row('Tfc', 'Tfc', '°C')}\n"
            f"\n"
            f"Napomenuti Filip: {napomenutiF if napomenutiF is not None else 0}\n"
            f"Napomenuti Vitek: {napomenutiV if napomenutiV is not None else 0}\n"
        )

    def reset_stats(self):
        for stat in self.stats.values():
            stat.update({"min": float("inf"), "max": float("-inf"), "avg": 0, "count": 0, "sum": 0})
