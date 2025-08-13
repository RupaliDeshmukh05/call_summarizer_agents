"""Frontend module for Call Center Dashboard"""

from .dashboard import CallCenterDashboard
from .components import (
    CallMetricsCard,
    AgentStatusCard,
    QualityScoreChart,
    CallVolumeChart
)

__all__ = [
    "CallCenterDashboard",
    "CallMetricsCard",
    "AgentStatusCard", 
    "QualityScoreChart",
    "CallVolumeChart"
]