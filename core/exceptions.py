"""Custom exceptions for the Call Center System"""


class CallCenterException(Exception):
    """Base exception for all call center errors"""
    pass


class AgentException(CallCenterException):
    """Exception raised by agents"""
    pass


class TranscriptionException(CallCenterException):
    """Exception raised during transcription"""
    pass


class RoutingException(CallCenterException):
    """Exception raised during call routing"""
    pass


class DatabaseException(CallCenterException):
    """Exception raised during database operations"""
    pass


class CommunicationException(CallCenterException):
    """Exception raised during inter-agent communication"""
    pass


class AuthenticationException(CallCenterException):
    """Exception raised during authentication"""
    pass


class ValidationException(CallCenterException):
    """Exception raised during data validation"""
    pass