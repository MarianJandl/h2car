from textual.app import ComposeResult
from textual.containers import ScrollableContainer, Vertical
from textual.widgets import Static
import json
from pathlib import Path
import datetime

def load_error_config():
    """Load error configuration from file"""
    config_path = Path("config/error_config.json")
    default_config = {
        "error_codes": [
            {
                "code": ["0x0", "0"],
                "priority": "info",
                "message": "OK - System operational",
                "action": None
            }
        ],
        "conditions": []
    }
    
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                return {**default_config, **config}
        except Exception:
            pass
    
    # Create default config file if it doesn't exist
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, 'w') as f:
        json.dump(default_config, f, indent=2)
    
    return default_config

class ErrorStatus(Static):
    def __init__(self):
        super().__init__()
        self.config = load_error_config()
        
    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("[bold]Error Status[/bold]\n", id="error_header")
            with ScrollableContainer(id="error_scroll"):
                yield Static(id="error_list")
    
    def reload_config(self):
        """Reload error codes from config"""
        self.config = load_error_config()
    
    def find_error_info(self, err_code):
        """Find error information from config"""
        for error in self.config.get("error_codes", []):
            if err_code in error["code"]:
                return error
        return None
    
    def parse_condition_string(self, condition_str):
        """Parse condition string like 'warning: Vbat < 8: Message here'"""
        try:
            parts = condition_str.split(":", 2)
            if len(parts) != 3:
                return None
            
            priority = parts[0].strip()
            condition_expr = parts[1].strip()
            message_template = parts[2].strip()
            
            return {
                "priority": priority,
                "expression": condition_expr,
                "message": message_template
            }
        except Exception:
            return None
    
    def evaluate_expression(self, expr, data):
        """Evaluate a condition expression like 'Vbat < 8' or 'Vfc < 10 & Vfc > 8'"""
        try:
            # Split by & (AND) or | (OR)
            if " & " in expr:
                conditions = expr.split(" & ")
                operator = "and"
            elif " | " in expr:
                conditions = expr.split(" | ")
                operator = "or"
            else:
                conditions = [expr]
                operator = "single"
            
            results = []
            for condition in conditions:
                condition = condition.strip()
                
                # Parse single condition
                for op in ["<=", ">=", "!=", "==", "<", ">"]:
                    if op in condition:
                        var, threshold = condition.split(op)
                        var = var.strip()
                        threshold = float(threshold.strip())
                        
                        if var not in data:
                            return False
                        
                        try:
                            value = float(data[var])
                        except (ValueError, TypeError):
                            return False
                        
                        # Evaluate
                        if op == "<":
                            results.append(value < threshold)
                        elif op == ">":
                            results.append(value > threshold)
                        elif op == "<=":
                            results.append(value <= threshold)
                        elif op == ">=":
                            results.append(value >= threshold)
                        elif op == "==":
                            results.append(value == threshold)
                        elif op == "!=":
                            results.append(value != threshold)
                        break
            
            # Combine results
            if operator == "and":
                return all(results)
            elif operator == "or":
                return any(results)
            else:
                return results[0] if results else False
                
        except Exception:
            return False
    
    def format_message(self, template, data):
        """Replace {variable} placeholders in message with actual values"""
        try:
            import re
            variables = re.findall(r'\{(\w+)\}', template)
            
            message = template
            for var in variables:
                if var in data:
                    try:
                        value = float(data[var])
                        message = message.replace(f"{{{var}}}", f"{value:.2f}")
                    except (ValueError, TypeError):
                        message = message.replace(f"{{{var}}}", str(data[var]))
            
            return message
        except Exception:
            return template
    
    def check_conditions(self, data):
        """Check all condition-based alerts"""
        alerts = []
        
        for condition_str in self.config.get("conditions", []):
            parsed = self.parse_condition_string(condition_str)
            if not parsed:
                continue
            
            if self.evaluate_expression(parsed["expression"], data):
                message = self.format_message(parsed["message"], data)
                alert = {
                    "priority": parsed["priority"],
                    "message": message,
                    "type": "condition"
                }
                alerts.append(alert)
        
        return alerts
    
    def get_priority_style(self, priority):
        """Get color and symbol based on priority"""
        styles = {
            "info": ("green", ""),
            "warning": ("yellow", ""),
            "error": ("red", ""),
            "critical": ("bold red", "")
        }
        return styles.get(priority, ("white", "•"))
    
    def get_priority_value(self, priority):
        """Get numeric value for priority sorting (higher = more severe)"""
        priority_values = {
            "info": 0,
            "warning": 1,
            "error": 2,
            "critical": 3
        }
        return priority_values.get(priority, 0)
    
    def update_status(self, data, nodata):
        if data is None:
            error_list = self.query_one("#error_list", Static)
            error_list.update(f"[dim]No data received ({nodata} cycles)[/dim]")
            return
        
        display_parts = []
        
        # ALWAYS show error code first
        err_code = data.get('Di', 'unknown')
        error_info = self.find_error_info(err_code)
        
        if error_info:
            color, symbol = self.get_priority_style(error_info["priority"])
            display_parts.append(f"[bold]Error Code:[/bold] [{color}]{symbol} {error_info['message']}[/{color}]")
        elif err_code not in ["0x0", "0"]:
            color, symbol = self.get_priority_style("critical")
            display_parts.append(f"[bold]Error Code:[/bold] [{color}]{symbol} Unknown error code: {err_code}[/{color}]")
        else:
            color, symbol = self.get_priority_style("info")
            display_parts.append(f"[bold]Error Code:[/bold] [{color}]{symbol} OK - System operational[/{color}]")
        
        # Check conditions and sort by priority
        condition_alerts = self.check_conditions(data)
        condition_alerts.sort(key=lambda x: self.get_priority_value(x["priority"]), reverse=True)
        
        # Show condition alerts if any
        if condition_alerts:
            display_parts.append("\n[bold]Alerts:[/bold]")
            for alert in condition_alerts:
                color, symbol = self.get_priority_style(alert["priority"])
                display_parts.append(f"[{color}]{symbol} {alert['message']}[/{color}]")
        
        error_list = self.query_one("#error_list", Static)
        error_list.update("\n".join(display_parts))