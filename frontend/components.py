"""Reusable Dashboard Components"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta


class CallMetricsCard:
    """Component for displaying call metrics"""
    
    @staticmethod
    def render(title: str, value: Any, icon: str, change: str = "", color: str = "blue"):
        """Render a metrics card"""
        with st.container():
            st.markdown(f"""
            <div style="
                background-color: white;
                padding: 1rem;
                border-radius: 0.5rem;
                border-left: 4px solid {color};
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                margin: 0.5rem 0;
            ">
                <div style="display: flex; align-items: center; margin-bottom: 0.5rem;">
                    <span style="font-size: 1.5rem; margin-right: 0.5rem;">{icon}</span>
                    <h3 style="margin: 0; color: #333; font-size: 0.9rem;">{title}</h3>
                </div>
                <div style="font-size: 2rem; font-weight: bold; color: #333; margin-bottom: 0.5rem;">
                    {value}
                </div>
                {f'<div style="font-size: 0.8rem; color: #666;">{change}</div>' if change else ''}
            </div>
            """, unsafe_allow_html=True)


class AgentStatusCard:
    """Component for displaying agent status"""
    
    @staticmethod
    def render(agent_data: Dict[str, Any]):
        """Render agent status card"""
        status_color = {
            "available": "green",
            "busy": "orange", 
            "offline": "red"
        }.get(agent_data.get("status", "offline").lower(), "gray")
        
        with st.container():
            st.markdown(f"""
            <div style="
                background-color: white;
                padding: 1rem;
                border-radius: 0.5rem;
                border: 1px solid #e0e0e0;
                margin: 0.5rem 0;
            ">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <h4 style="margin: 0; color: #333;">{agent_data.get('name', 'Unknown')}</h4>
                        <p style="margin: 0.25rem 0; color: #666; font-size: 0.8rem;">
                            {agent_data.get('specialization', 'General')}
                        </p>
                    </div>
                    <div style="
                        background-color: {status_color};
                        color: white;
                        padding: 0.25rem 0.5rem;
                        border-radius: 1rem;
                        font-size: 0.7rem;
                        font-weight: bold;
                    ">
                        {agent_data.get('status', 'Offline').upper()}
                    </div>
                </div>
                <div style="margin-top: 0.5rem; display: flex; justify-content: space-between;">
                    <span style="font-size: 0.8rem; color: #666;">
                        Calls: {agent_data.get('calls_today', 0)}
                    </span>
                    <span style="font-size: 0.8rem; color: #666;">
                        Quality: {agent_data.get('quality_score', 0)}
                    </span>
                </div>
            </div>
            """, unsafe_allow_html=True)


class QualityScoreChart:
    """Component for quality score visualization"""
    
    @staticmethod
    def render(data: List[Dict[str, Any]], title: str = "Quality Scores"):
        """Render quality score chart"""
        if not data:
            st.info("No quality data available")
            return
        
        df = pd.DataFrame(data)
        
        # Determine chart type based on data
        if 'date' in df.columns or 'timestamp' in df.columns:
            # Time series chart
            date_col = 'date' if 'date' in df.columns else 'timestamp'
            fig = px.line(
                df, 
                x=date_col, 
                y='score',
                title=title,
                markers=True,
                color_discrete_sequence=['#1f77b4']
            )
            fig.add_hline(y=85, line_dash="dash", annotation_text="Target (85)")
            
        else:
            # Bar chart
            fig = px.bar(
                df,
                x='category' if 'category' in df.columns else df.columns[0],
                y='score',
                title=title,
                color='score',
                color_continuous_scale='RdYlGn'
            )
        
        fig.update_layout(
            height=400,
            showlegend=False,
            title_font_size=16
        )
        
        st.plotly_chart(fig, use_container_width=True)


class CallVolumeChart:
    """Component for call volume visualization"""
    
    @staticmethod
    def render(data: List[Dict[str, Any]], chart_type: str = "line"):
        """Render call volume chart"""
        if not data:
            st.info("No call volume data available")
            return
        
        df = pd.DataFrame(data)
        
        if chart_type == "line":
            fig = px.line(
                df,
                x='time' if 'time' in df.columns else df.columns[0],
                y='volume' if 'volume' in df.columns else df.columns[1],
                title="Call Volume Over Time",
                markers=True
            )
        elif chart_type == "bar":
            fig = px.bar(
                df,
                x='time' if 'time' in df.columns else df.columns[0],
                y='volume' if 'volume' in df.columns else df.columns[1],
                title="Call Volume"
            )
        else:
            fig = px.area(
                df,
                x='time' if 'time' in df.columns else df.columns[0],
                y='volume' if 'volume' in df.columns else df.columns[1],
                title="Call Volume Trend"
            )
        
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)


class CallDetailsPanel:
    """Component for displaying detailed call information"""
    
    @staticmethod
    def render(call_data: Dict[str, Any]):
        """Render call details panel"""
        if not call_data:
            st.info("No call selected")
            return
        
        with st.expander("📋 Call Information", expanded=True):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Basic Information**")
                st.text(f"Call ID: {call_data.get('id', 'N/A')}")
                st.text(f"Status: {call_data.get('status', 'N/A')}")
                st.text(f"Priority: {call_data.get('priority', 'N/A')}")
                st.text(f"Duration: {call_data.get('duration', 'N/A')}")
            
            with col2:
                st.markdown("**Customer Information**")
                st.text(f"Name: {call_data.get('customer_name', 'N/A')}")
                st.text(f"Phone: {call_data.get('customer_phone', 'N/A')}")
                st.text(f"Account: {call_data.get('account_number', 'N/A')}")
        
        if call_data.get('summary'):
            with st.expander("📝 Summary", expanded=True):
                st.write(call_data['summary'])
        
        if call_data.get('transcript'):
            with st.expander("📜 Transcript"):
                st.code(call_data['transcript'], language=None)


class LiveMetricsPanel:
    """Component for real-time metrics display"""
    
    @staticmethod
    def render():
        """Render live metrics panel"""
        st.markdown("### 🔴 Live Metrics")
        
        # Create columns for live metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            # Active calls gauge
            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=12,
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': "Active Calls"},
                gauge={
                    'axis': {'range': [None, 50]},
                    'bar': {'color': "darkblue"},
                    'steps': [
                        {'range': [0, 25], 'color': "lightgray"},
                        {'range': [25, 50], 'color': "gray"}
                    ],
                    'threshold': {
                        'line': {'color': "red", 'width': 4},
                        'thickness': 0.75,
                        'value': 40
                    }
                }
            ))
            fig.update_layout(height=200, margin=dict(l=0, r=0, t=30, b=0))
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Queue size
            queue_size = 3
            st.metric("Queue Size", queue_size, delta="+1")
        
        with col3:
            # Average wait time
            avg_wait = "2:45"
            st.metric("Avg Wait Time", avg_wait, delta="-0:30")
        
        with col4:
            # Available agents
            available_agents = 8
            st.metric("Available Agents", available_agents, delta="-2")


class AlertsPanel:
    """Component for displaying system alerts"""
    
    @staticmethod
    def render(alerts: List[Dict[str, Any]] = None):
        """Render alerts panel"""
        if not alerts:
            alerts = [
                {
                    "type": "warning",
                    "message": "High call volume detected",
                    "timestamp": "2 minutes ago"
                },
                {
                    "type": "info", 
                    "message": "Agent John Smith started shift",
                    "timestamp": "15 minutes ago"
                },
                {
                    "type": "error",
                    "message": "Quality score below threshold for Call-123",
                    "timestamp": "1 hour ago"
                }
            ]
        
        st.markdown("### 🚨 System Alerts")
        
        for alert in alerts:
            alert_color = {
                "error": "🔴",
                "warning": "🟡", 
                "info": "🔵",
                "success": "🟢"
            }.get(alert["type"], "⚪")
            
            with st.container():
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"{alert_color} {alert['message']}")
                with col2:
                    st.caption(alert["timestamp"])
                st.divider()


class PerformanceMetricsTable:
    """Component for displaying performance metrics in table format"""
    
    @staticmethod
    def render(data: List[Dict[str, Any]], title: str = "Performance Metrics"):
        """Render performance metrics table"""
        if not data:
            st.info("No performance data available")
            return
        
        st.markdown(f"### {title}")
        
        df = pd.DataFrame(data)
        
        # Style the dataframe
        styled_df = df.style.format({
            'quality_score': '{:.1f}',
            'duration': '{:.2f}',
            'resolution_rate': '{:.1%}'
        }).background_gradient(
            subset=['quality_score'], 
            cmap='RdYlGn'
        )
        
        st.dataframe(styled_df, use_container_width=True, hide_index=True)


class TrendAnalysisChart:
    """Component for trend analysis visualization"""
    
    @staticmethod
    def render(
        data: List[Dict[str, Any]], 
        x_col: str, 
        y_col: str, 
        title: str = "Trend Analysis",
        show_trend_line: bool = True
    ):
        """Render trend analysis chart"""
        if not data:
            st.info("No trend data available")
            return
        
        df = pd.DataFrame(data)
        
        # Create base chart
        fig = px.scatter(
            df, 
            x=x_col, 
            y=y_col,
            title=title,
            trendline="ols" if show_trend_line else None
        )
        
        # Add moving average if enough data points
        if len(df) > 5:
            df['moving_avg'] = df[y_col].rolling(window=5).mean()
            fig.add_trace(
                go.Scatter(
                    x=df[x_col],
                    y=df['moving_avg'],
                    name='Moving Average',
                    line=dict(color='red', dash='dash')
                )
            )
        
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)