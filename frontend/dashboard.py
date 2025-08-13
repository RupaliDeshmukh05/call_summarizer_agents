"""Streamlit Dashboard for Call Center System"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import json

from database import get_database
from core import get_logger
from .components import CallMetricsCard, AgentStatusCard, QualityScoreChart, CallVolumeChart


class CallCenterDashboard:
    """Main dashboard for Call Center System"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.db = None
        
        # Initialize Streamlit config
        st.set_page_config(
            page_title="AI Call Center Dashboard",
            page_icon="📞",
            layout="wide",
            initial_sidebar_state="expanded"
        )
    
    def run(self) -> None:
        """Run the dashboard"""
        try:
            self._initialize_db()
            self._render_dashboard()
        except Exception as e:
            st.error(f"Dashboard error: {e}")
            self.logger.error(f"Dashboard error: {e}")
    
    def _initialize_db(self) -> None:
        """Initialize database connection"""
        try:
            self.db = get_database()
        except Exception as e:
            st.error("Database not initialized. Please start the system first.")
            st.stop()
    
    def _render_dashboard(self) -> None:
        """Render the main dashboard"""
        # Header
        st.title("🤖 AI Call Center Dashboard")
        st.markdown("---")
        
        # Sidebar
        self._render_sidebar()
        
        # Main content based on selected page
        page = st.session_state.get('page', 'overview')
        
        if page == 'overview':
            self._render_overview()
        elif page == 'calls':
            self._render_calls()
        elif page == 'agents':
            self._render_agents()
        elif page == 'quality':
            self._render_quality()
        elif page == 'analytics':
            self._render_analytics()
        elif page == 'settings':
            self._render_settings()
    
    def _render_sidebar(self) -> None:
        """Render sidebar navigation"""
        with st.sidebar:
            st.header("📊 Navigation")
            
            pages = {
                'overview': '📈 Overview',
                'calls': '📞 Live Calls',
                'agents': '👥 Agents',
                'quality': '⭐ Quality',
                'analytics': '📊 Analytics',
                'settings': '⚙️ Settings'
            }
            
            selected = st.radio(
                "Select Page",
                options=list(pages.keys()),
                format_func=lambda x: pages[x],
                key='page'
            )
            
            st.markdown("---")
            
            # Refresh controls
            st.subheader("🔄 Refresh")
            if st.button("Refresh Data"):
                st.experimental_rerun()
            
            auto_refresh = st.checkbox("Auto Refresh (30s)")
            if auto_refresh:
                # Auto-refresh every 30 seconds
                import time
                time.sleep(30)
                st.experimental_rerun()
            
            st.markdown("---")
            
            # System status
            self._render_system_status()
    
    def _render_system_status(self) -> None:
        """Render system status in sidebar"""
        st.subheader("🔧 System Status")
        
        try:
            # Mock system status (in production, get from actual system)
            status = {
                "database": "🟢 Connected",
                "message_bus": "🟢 Active",
                "agents": "🟢 Running",
                "voice_service": "🟡 Limited"
            }
            
            for service, status_text in status.items():
                st.text(f"{service.title()}: {status_text}")
                
        except Exception as e:
            st.error("Unable to fetch system status")
    
    def _render_overview(self) -> None:
        """Render overview dashboard"""
        st.header("📈 System Overview")
        
        # Key metrics row
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            self._render_metric_card("Active Calls", 12, "📞", "+2 from last hour")
        
        with col2:
            self._render_metric_card("Available Agents", 8, "👥", "2 specialists online")
        
        with col3:
            self._render_metric_card("Avg Quality Score", 87, "⭐", "+5% this week")
        
        with col4:
            self._render_metric_card("Resolution Rate", "94%", "✅", "+2% this month")
        
        st.markdown("---")
        
        # Charts row
        col1, col2 = st.columns(2)
        
        with col1:
            self._render_call_volume_chart()
        
        with col2:
            self._render_quality_trend_chart()
        
        # Recent activity
        st.subheader("📋 Recent Activity")
        self._render_recent_activity()
    
    def _render_calls(self) -> None:
        """Render live calls page"""
        st.header("📞 Live Calls")
        
        # Controls
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            search = st.text_input("🔍 Search calls", placeholder="Call ID, customer name, or phone")
        
        with col2:
            status_filter = st.selectbox("Status", ["All", "Active", "Queued", "Completed"])
        
        with col3:
            priority_filter = st.selectbox("Priority", ["All", "Urgent", "High", "Normal", "Low"])
        
        # Active calls table
        st.subheader("🔴 Active Calls")
        self._render_active_calls_table()
        
        st.markdown("---")
        
        # Call details
        if st.session_state.get('selected_call'):
            self._render_call_details(st.session_state.selected_call)
    
    def _render_agents(self) -> None:
        """Render agents page"""
        st.header("👥 Agents")
        
        # Agent status overview
        col1, col2, col3 = st.columns(3)
        
        with col1:
            self._render_metric_card("Total Agents", 15, "👥", "3 new this month")
        
        with col2:
            self._render_metric_card("Available", 8, "🟢", "53% utilization")
        
        with col3:
            self._render_metric_card("Average Rating", 4.2, "⭐", "out of 5.0")
        
        # Agent performance table
        st.subheader("📊 Agent Performance")
        self._render_agent_performance_table()
        
        # Agent details
        selected_agent = st.selectbox(
            "Select Agent for Details",
            ["All", "John Smith", "Jane Doe", "AI Agent 1", "Mike Johnson"]
        )
        
        if selected_agent != "All":
            self._render_agent_details(selected_agent)
    
    def _render_quality(self) -> None:
        """Render quality page"""
        st.header("⭐ Quality Management")
        
        # Quality metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            self._render_metric_card("Avg Score", 87, "⭐", "+2 points")
        
        with col2:
            self._render_metric_card("Compliance", "96%", "✅", "+1% this week")
        
        with col3:
            self._render_metric_card("Coaching Needed", 3, "📚", "2 urgent")
        
        with col4:
            self._render_metric_card("Customer Satisfaction", "4.5/5", "😊", "+0.2 this month")
        
        # Quality trends
        st.subheader("📈 Quality Trends")
        self._render_quality_trends()
        
        # Quality breakdown
        col1, col2 = st.columns(2)
        
        with col1:
            self._render_quality_dimensions_chart()
        
        with col2:
            self._render_quality_distribution_chart()
        
        # Low scoring calls
        st.subheader("⚠️ Calls Requiring Attention")
        self._render_low_quality_calls()
    
    def _render_analytics(self) -> None:
        """Render analytics page"""
        st.header("📊 Advanced Analytics")
        
        # Date range selector
        col1, col2 = st.columns(2)
        
        with col1:
            start_date = st.date_input("Start Date", value=datetime.now() - timedelta(days=30))
        
        with col2:
            end_date = st.date_input("End Date", value=datetime.now())
        
        # Analytics tabs
        tab1, tab2, tab3, tab4 = st.tabs(["📈 Call Volume", "⏱️ Performance", "🎯 Outcomes", "💰 ROI"])
        
        with tab1:
            self._render_call_volume_analytics(start_date, end_date)
        
        with tab2:
            self._render_performance_analytics(start_date, end_date)
        
        with tab3:
            self._render_outcome_analytics(start_date, end_date)
        
        with tab4:
            self._render_roi_analytics(start_date, end_date)
    
    def _render_settings(self) -> None:
        """Render settings page"""
        st.header("⚙️ System Settings")
        
        # Settings tabs
        tab1, tab2, tab3 = st.tabs(["🔧 System", "👥 Agents", "🎯 Quality"])
        
        with tab1:
            self._render_system_settings()
        
        with tab2:
            self._render_agent_settings()
        
        with tab3:
            self._render_quality_settings()
    
    def _render_metric_card(self, title: str, value: Any, icon: str, subtitle: str = "") -> None:
        """Render a metric card"""
        st.metric(
            label=f"{icon} {title}",
            value=str(value),
            delta=subtitle if subtitle else None
        )
    
    def _render_call_volume_chart(self) -> None:
        """Render call volume chart"""
        st.subheader("📊 Call Volume (Last 24 Hours)")
        
        # Generate sample data
        hours = list(range(24))
        calls = [
            15, 18, 12, 8, 5, 3, 2, 4, 8, 12,
            20, 25, 30, 28, 24, 26, 22, 19, 17, 15,
            12, 10, 8, 6
        ]
        
        df = pd.DataFrame({
            'Hour': [f"{h:02d}:00" for h in hours],
            'Calls': calls
        })
        
        fig = px.line(
            df, x='Hour', y='Calls',
            title="Hourly Call Volume",
            markers=True
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
    
    def _render_quality_trend_chart(self) -> None:
        """Render quality trend chart"""
        st.subheader("⭐ Quality Trends (Last 7 Days)")
        
        # Generate sample data
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        scores = [85, 87, 89, 86, 88, 90, 87]
        
        df = pd.DataFrame({
            'Day': days,
            'Quality Score': scores
        })
        
        fig = px.bar(
            df, x='Day', y='Quality Score',
            title="Daily Quality Scores",
            color='Quality Score',
            color_continuous_scale='RdYlGn'
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
    
    def _render_recent_activity(self) -> None:
        """Render recent activity list"""
        activities = [
            {"time": "2 min ago", "event": "📞 New call from +1-555-0123", "status": "active"},
            {"time": "5 min ago", "event": "✅ Call CALL-001 completed with score 92", "status": "completed"},
            {"time": "8 min ago", "event": "🔄 Call CALL-002 transferred to specialist", "status": "transferred"},
            {"time": "12 min ago", "event": "⚠️ Call CALL-003 escalated to supervisor", "status": "escalated"},
            {"time": "15 min ago", "event": "📊 Quality assessment completed for CALL-004", "status": "info"}
        ]
        
        for activity in activities:
            with st.container():
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.text(activity["event"])
                with col2:
                    st.caption(activity["time"])
                st.divider()
    
    def _render_active_calls_table(self) -> None:
        """Render active calls table"""
        # Sample data
        calls_data = [
            {
                "Call ID": "CALL-001",
                "Customer": "John Smith",
                "Agent": "AI Agent 1",
                "Duration": "00:03:45",
                "Status": "🔴 Active",
                "Priority": "High"
            },
            {
                "Call ID": "CALL-002", 
                "Customer": "Jane Doe",
                "Agent": "Mike Johnson",
                "Duration": "00:01:22",
                "Status": "🔴 Active",
                "Priority": "Normal"
            },
            {
                "Call ID": "CALL-003",
                "Customer": "Bob Wilson",
                "Agent": "Queue",
                "Duration": "00:00:45",
                "Status": "🟡 Queued",
                "Priority": "Urgent"
            }
        ]
        
        df = pd.DataFrame(calls_data)
        
        # Interactive table with selection
        selected_row = st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row"
        )
        
        if selected_row.selection.rows:
            selected_call_id = df.iloc[selected_row.selection.rows[0]]["Call ID"]
            st.session_state.selected_call = selected_call_id
    
    def _render_call_details(self, call_id: str) -> None:
        """Render detailed call information"""
        st.subheader(f"📋 Call Details: {call_id}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Customer Information**")
            st.text("Name: John Smith")
            st.text("Phone: +1-555-0123")
            st.text("Account: ACC-12345")
            st.text("Language: English")
            
            st.markdown("**Call Information**")
            st.text("Started: 10:45 AM")
            st.text("Duration: 00:03:45")
            st.text("Priority: High")
            st.text("Category: Technical Support")
        
        with col2:
            st.markdown("**Real-time Summary**")
            st.info("Customer reporting login issues with mobile app. Agent provided troubleshooting steps.")
            
            st.markdown("**Key Points**")
            st.text("• App crashes on startup")
            st.text("• Already tried basic restart")
            st.text("• Account verified successfully")
            
            st.markdown("**Action Items**")
            st.text("• Clear app cache")
            st.text("• Update to latest version")
            st.text("• Follow up in 24 hours")
        
        # Real-time transcript (if available)
        if st.checkbox("Show Live Transcript"):
            st.markdown("**Live Transcript**")
            transcript_text = """
            Agent: Thank you for calling. How can I help you today?
            Customer: Hi, I'm having trouble with your mobile app. It keeps crashing.
            Agent: I'm sorry to hear that. Let me help you troubleshoot this issue.
            Customer: I've already tried restarting my phone, but it didn't work.
            Agent: I understand. Let's try clearing the app cache first...
            """
            st.code(transcript_text, language=None)
    
    def _render_agent_performance_table(self) -> None:
        """Render agent performance table"""
        agents_data = [
            {
                "Agent": "John Smith",
                "Status": "🟢 Available",
                "Calls Today": 12,
                "Avg Quality": 89,
                "Avg Duration": "4:32",
                "Specialization": "Technical"
            },
            {
                "Agent": "Jane Doe",
                "Status": "🔴 On Call",
                "Calls Today": 8,
                "Avg Quality": 92,
                "Avg Duration": "3:45",
                "Specialization": "Billing"
            },
            {
                "Agent": "AI Agent 1",
                "Status": "🟢 Available",
                "Calls Today": 25,
                "Avg Quality": 85,
                "Avg Duration": "2:15",
                "Specialization": "General"
            },
            {
                "Agent": "Mike Johnson",
                "Status": "🔴 On Call",
                "Calls Today": 10,
                "Avg Quality": 88,
                "Avg Duration": "5:20",
                "Specialization": "Technical"
            }
        ]
        
        df = pd.DataFrame(agents_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
    
    def _render_agent_details(self, agent_name: str) -> None:
        """Render detailed agent information"""
        st.subheader(f"👤 Agent Details: {agent_name}")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Calls Today", 12, "+2")
            st.metric("Quality Score", 89, "+1")
        
        with col2:
            st.metric("Avg Duration", "4:32", "-0:15")
            st.metric("Customer Rating", "4.5/5", "+0.1")
        
        with col3:
            st.metric("Resolution Rate", "94%", "+2%")
            st.metric("Active Since", "08:30 AM", "")
        
        # Performance chart for selected agent
        st.subheader("📈 Performance Trend")
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
        scores = [87, 89, 91, 88, 89]
        
        fig = px.line(
            x=days, y=scores,
            title=f"Quality Trend - {agent_name}",
            markers=True
        )
        st.plotly_chart(fig, use_container_width=True)
    
    def _render_quality_trends(self) -> None:
        """Render quality trends"""
        # Sample data for quality trends
        dates = pd.date_range('2024-01-01', periods=30, freq='D')
        scores = [85 + (i % 10) + (i // 10) * 2 + (5 if i % 7 == 0 else 0) for i in range(30)]
        
        df = pd.DataFrame({
            'Date': dates,
            'Quality Score': scores
        })
        
        fig = px.line(
            df, x='Date', y='Quality Score',
            title="Quality Score Trend (Last 30 Days)",
            markers=True
        )
        fig.add_hline(y=85, line_dash="dash", annotation_text="Target (85)")
        st.plotly_chart(fig, use_container_width=True)
    
    def _render_quality_dimensions_chart(self) -> None:
        """Render quality dimensions breakdown"""
        st.subheader("📊 Quality Dimensions")
        
        dimensions = [
            'Greeting', 'Identity Verification', 'Issue Understanding',
            'Solution Provided', 'Professionalism', 'Empathy', 'Compliance', 'Closure'
        ]
        scores = [92, 88, 85, 89, 91, 87, 95, 90]
        
        df = pd.DataFrame({
            'Dimension': dimensions,
            'Score': scores
        })
        
        fig = px.bar(
            df, x='Score', y='Dimension', orientation='h',
            title="Average Scores by Dimension",
            color='Score',
            color_continuous_scale='RdYlGn'
        )
        st.plotly_chart(fig, use_container_width=True)
    
    def _render_quality_distribution_chart(self) -> None:
        """Render quality score distribution"""
        st.subheader("📈 Score Distribution")
        
        # Generate sample distribution data
        import numpy as np
        scores = np.random.normal(87, 8, 100).astype(int)
        scores = np.clip(scores, 0, 100)
        
        fig = px.histogram(
            x=scores,
            nbins=20,
            title="Quality Score Distribution",
            labels={'x': 'Quality Score', 'y': 'Count'}
        )
        fig.add_vline(x=85, line_dash="dash", annotation_text="Target")
        st.plotly_chart(fig, use_container_width=True)
    
    def _render_low_quality_calls(self) -> None:
        """Render table of low quality calls"""
        low_quality_data = [
            {
                "Call ID": "CALL-045",
                "Agent": "John Smith", 
                "Score": 65,
                "Issues": "Incomplete verification, Poor closure",
                "Action": "Coaching scheduled"
            },
            {
                "Call ID": "CALL-067",
                "Agent": "Jane Doe",
                "Score": 72,
                "Issues": "Lack of empathy, Rushed resolution",
                "Action": "Manager review"
            }
        ]
        
        df = pd.DataFrame(low_quality_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
    
    def _render_call_volume_analytics(self, start_date, end_date) -> None:
        """Render call volume analytics"""
        st.subheader("📈 Call Volume Analysis")
        
        # Generate sample hourly data
        hours = list(range(24))
        volume_data = [
            {"Hour": f"{h:02d}:00", "Calls": 10 + h + (h % 6) * 3} 
            for h in hours
        ]
        
        df = pd.DataFrame(volume_data)
        
        fig = px.bar(
            df, x='Hour', y='Calls',
            title="Average Hourly Call Volume"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    def _render_performance_analytics(self, start_date, end_date) -> None:
        """Render performance analytics"""
        st.subheader("⏱️ Performance Metrics")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Average handle time
            agents = ["John", "Jane", "Mike", "AI Agent 1", "AI Agent 2"]
            times = [4.5, 3.8, 5.2, 2.1, 2.3]
            
            fig = px.bar(
                x=agents, y=times,
                title="Average Handle Time (minutes)",
                labels={'x': 'Agent', 'y': 'Minutes'}
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Resolution rates
            rates = [94, 96, 89, 87, 92]
            
            fig = px.bar(
                x=agents, y=rates,
                title="Resolution Rate (%)",
                labels={'x': 'Agent', 'y': 'Percentage'},
                color=rates,
                color_continuous_scale='RdYlGn'
            )
            st.plotly_chart(fig, use_container_width=True)
    
    def _render_outcome_analytics(self, start_date, end_date) -> None:
        """Render outcome analytics"""
        st.subheader("🎯 Call Outcomes")
        
        outcomes = ["Resolved", "Escalated", "Callback Scheduled", "Transferred", "Abandoned"]
        counts = [450, 75, 30, 45, 25]
        
        fig = px.pie(
            values=counts, names=outcomes,
            title="Call Outcome Distribution"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    def _render_roi_analytics(self, start_date, end_date) -> None:
        """Render ROI analytics"""
        st.subheader("💰 Return on Investment")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Cost per Call", "$12.50", "-$2.30")
            st.metric("Agent Utilization", "87%", "+5%")
            st.metric("Customer Satisfaction", "4.5/5", "+0.3")
        
        with col2:
            st.metric("Monthly Savings", "$45,000", "+15%")
            st.metric("Automation Rate", "35%", "+8%")
            st.metric("Average Revenue", "$890", "+12%")
    
    def _render_system_settings(self) -> None:
        """Render system settings"""
        st.subheader("🔧 System Configuration")
        
        st.slider("Max Concurrent Calls", 1, 100, 50)
        st.slider("Quality Score Threshold", 0, 100, 85)
        st.selectbox("Default Language", ["English", "Spanish", "French"])
        st.checkbox("Enable Auto-Escalation")
        st.number_input("Escalation Threshold", min_value=0, max_value=100, value=70)
        
        if st.button("Save System Settings"):
            st.success("Settings saved successfully!")
    
    def _render_agent_settings(self) -> None:
        """Render agent settings"""
        st.subheader("👥 Agent Configuration")
        
        st.number_input("Default Agent Capacity", min_value=1, max_value=20, value=5)
        st.selectbox("Routing Algorithm", ["Skill-based", "Round-robin", "Least-busy"])
        st.slider("Agent Timeout (seconds)", 30, 600, 300)
        st.checkbox("Enable Agent Performance Tracking")
        
        if st.button("Save Agent Settings"):
            st.success("Agent settings saved!")
    
    def _render_quality_settings(self) -> None:
        """Render quality settings"""
        st.subheader("⭐ Quality Configuration")
        
        st.slider("Minimum Quality Score", 0, 100, 70)
        st.checkbox("Enable Real-time Quality Scoring")
        st.checkbox("Auto-generate Coaching Recommendations")
        st.selectbox("Quality Model", ["Standard", "Advanced", "Custom"])
        
        if st.button("Save Quality Settings"):
            st.success("Quality settings saved!")


def main():
    """Main function to run the dashboard"""
    dashboard = CallCenterDashboard()
    dashboard.run()


if __name__ == "__main__":
    main()