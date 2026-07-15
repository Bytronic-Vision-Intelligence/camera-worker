# -*- coding: 'unicode' -*-
# Copyright (c) 2024 KEYENCE CORPORATION. All rights reserved.
#
# Vendored unmodified from LJ-S_PyLib (KEYENCE LJ-S8000 Communication
# Library). Keep this file next to LJS8_IF.dll -- the DLL path below is
# resolved relative to this file's location, not via PATH.
import ctypes
from ctypes import cdll
import os.path


#########################################################
# Select the library according to the Operating System
#########################################################
envWindows = 1  # Set to 1 if the OS is Windows, to 0 if the OS is Linux

if envWindows:
    dll_name = "LJS8_IF.dll"    # For Windows
else:
    dll_name = "libljscom.so"   # For Linux

dllabspath = os.path.dirname(os.path.abspath(__file__))+os.path.sep+dll_name
mdll = cdll.LoadLibrary(dllabspath)


#########################################################
# Structure
#########################################################
class LJS8IF_ETHERNET_CONFIG(ctypes.Structure):
    _fields_ = [
        ("abyIpAddress", ctypes.c_ubyte * 4),
        ("wPortNo", ctypes.c_ushort),
        ("reserve", ctypes.c_ubyte * 2)]


class LJS8IF_TARGET_SETTING(ctypes.Structure):
    _fields_ = [
        ("byType", ctypes.c_ubyte),
        ("byCategory", ctypes.c_ubyte),
        ("byItem", ctypes.c_ubyte),
        ("reserve", ctypes.c_ubyte),
        ("byTarget1", ctypes.c_ubyte),
        ("byTarget2", ctypes.c_ubyte),
        ("byTarget3", ctypes.c_ubyte),
        ("byTarget4", ctypes.c_ubyte)]


class LJS8IF_HEIGHT_IMAGE_INFO(ctypes.Structure):
    _fields_ = [
        ("wXPointNum", ctypes.c_ushort),
        ("wYLineNum", ctypes.c_ushort),
        ("byLuminanceOutput", ctypes.c_ubyte),
        ("reserve", ctypes.c_ubyte * 3),
        ("nXStart", ctypes.c_int),
        ("dwPitchX", ctypes.c_uint),
        ("nYStart", ctypes.c_int),
        ("dwPitchY", ctypes.c_uint),
        ("reserve2", ctypes.c_ubyte * 4),
        ("dwPitchZ", ctypes.c_uint)]


class LJS8IF_PROFILE_HEADER(ctypes.Structure):
    _fields_ = [
        ("reserve", ctypes.c_uint),
        ("dwHeightImageNo", ctypes.c_uint),
        ("dwProfileNo", ctypes.c_int),
        ("byProcTimeout", ctypes.c_ubyte),
        ("reserve2", ctypes.c_ubyte * 11)]


class LJS8IF_PROFILE_FOOTER(ctypes.Structure):
    _fields_ = [
        ("reserve", ctypes.c_uint)]


class LJS8IF_GET_HEIGHT_IMAGE_PROFILE_REQUEST(ctypes.Structure):
    _fields_ = [
        ("reserve", ctypes.c_ubyte),
        ("byPositionMode", ctypes.c_ubyte),
        ("reserve2", ctypes.c_ubyte * 2),
        ("dwGetHeightImageNo", ctypes.c_uint),
        ("dwGetProfileNo", ctypes.c_uint),
        ("wGetProfileCount", ctypes.c_ushort),
        ("byErase", ctypes.c_ubyte),
        ("reserve3", ctypes.c_ubyte)]


class LJS8IF_GET_HEIGHT_IMAGE_PROFILE_RESPONSE(ctypes.Structure):
    _fields_ = [
        ("dwCurrentHeightImageNo", ctypes.c_uint),
        ("dwCurrentHeightImageProfileCount", ctypes.c_uint),
        ("dwOldestHeightImageNo", ctypes.c_uint),
        ("dwOldestHeightImageProfileCount", ctypes.c_uint),
        ("dwGetHeightImageNo", ctypes.c_uint),
        ("dwGetHeightImageProfileCount", ctypes.c_uint),
        ("dwGetHeightImageTopProfileNo", ctypes.c_uint),
        ("wGetProfileCount", ctypes.c_ushort),
        ("byCurrentHeightImageCommitted", ctypes.c_ubyte),
        ("reserve", ctypes.c_ubyte)]


class LJS8IF_HIGH_SPEED_PRE_START_REQ(ctypes.Structure):
    _fields_ = [
        ("bySendPosition", ctypes.c_ubyte),
        ("reserve", ctypes.c_ubyte * 3)]


#########################################################
# DLL Wrapper Function
#########################################################

LJS8IF_CALLBACK_SIMPLE_ARRAY = ctypes.CFUNCTYPE(
    ctypes.c_void_p,
    ctypes.POINTER(LJS8IF_PROFILE_HEADER),  # pProfileHeaderArray
    ctypes.POINTER(ctypes.c_ushort),        # pHeightProfileArray
    ctypes.POINTER(ctypes.c_ubyte),         # pLuminanceProfileArray
    ctypes.c_uint,                          # dwLuminanceEnable
    ctypes.c_uint,                          # dwProfileDataCount
    ctypes.c_uint,                          # dwCount
    ctypes.c_uint,                          # dwNotify
    ctypes.c_uint                           # dwUser
    )

if envWindows:
    # LJS8IF_Initialize
    LJS8IF_Initialize = mdll.LJS8IF_Initialize
    LJS8IF_Initialize.restype = ctypes.c_int
    LJS8IF_Initialize.argtypes = []

    # LJS8IF_Finalize
    LJS8IF_Finalize = mdll.LJS8IF_Finalize
    LJS8IF_Finalize.restype = ctypes.c_int
    LJS8IF_Finalize.argtypes = []

# LJS8IF_EthernetOpen
LJS8IF_EthernetOpen = mdll.LJS8IF_EthernetOpen
LJS8IF_EthernetOpen.restype = ctypes.c_int
LJS8IF_EthernetOpen.argtypes = [
    ctypes.c_int,                           # lDeviceId
    ctypes.POINTER(LJS8IF_ETHERNET_CONFIG)  # pEthernetConfig
    ]

# LJS8IF_CommunicationClose
LJS8IF_CommunicationClose = mdll.LJS8IF_CommunicationClose
LJS8IF_CommunicationClose.restype = ctypes.c_int
LJS8IF_CommunicationClose.argtypes = [
    ctypes.c_int                            # lDeviceId
    ]

# LJS8IF_Reboot
LJS8IF_Reboot = mdll.LJS8IF_Reboot
LJS8IF_Reboot.restype = ctypes.c_int
LJS8IF_Reboot.argtypes = [
    ctypes.c_int                            # lDeviceId
    ]

# LJS8IF_ReturnToFactorySetting
LJS8IF_ReturnToFactorySetting = mdll.LJS8IF_ReturnToFactorySetting
LJS8IF_ReturnToFactorySetting.restype = ctypes.c_int
LJS8IF_ReturnToFactorySetting.argtypes = [
    ctypes.c_int                            # lDeviceId
    ]

# LJS8IF_ControlLaser
LJS8IF_ControlLaser = mdll.LJS8IF_ControlLaser
LJS8IF_ControlLaser.restype = ctypes.c_int
LJS8IF_ControlLaser.argtypes = [
    ctypes.c_int,                           # lDeviceId
    ctypes.c_ubyte                          # byState
    ]

# LJS8IF_GetError
LJS8IF_GetError = mdll.LJS8IF_GetError
LJS8IF_GetError.restype = ctypes.c_int
LJS8IF_GetError.argtypes = [
    ctypes.c_int,                           # lDeviceId
    ctypes.c_ubyte,                         # byReceivedMax
    ctypes.POINTER(ctypes.c_ubyte),         # pbyErrCount
    ctypes.POINTER(ctypes.c_ushort)         # pwErrCode
    ]

# LJS8IF_ClearError
LJS8IF_ClearError = mdll.LJS8IF_ClearError
LJS8IF_ClearError.restype = ctypes.c_int
LJS8IF_ClearError.argtypes = [
    ctypes.c_int,                           # lDeviceId
    ctypes.c_ushort                         # wErrCode
    ]

# LJS8IF_GetHeadTemperature
LJS8IF_GetHeadTemperature = mdll.LJS8IF_GetHeadTemperature
LJS8IF_GetHeadTemperature.restype = ctypes.c_int
LJS8IF_GetHeadTemperature.argtypes = [
    ctypes.c_int,                           # lDeviceId
    ctypes.POINTER(ctypes.c_short),         # pnSensorTemperature
    ctypes.POINTER(ctypes.c_short),         # pnProcessorTemperature1
    ctypes.POINTER(ctypes.c_short),         # pnProcessorTemperature2
    ctypes.POINTER(ctypes.c_short),         # pnCaseTemperature
    ctypes.POINTER(ctypes.c_short)          # pnDriveUnitTemperature
    ]

# LJS8IF_GetHeadModel
LJS8IF_GetHeadModel = mdll.LJS8IF_GetHeadModel
LJS8IF_GetHeadModel.restype = ctypes.c_int
LJS8IF_GetHeadModel.argtypes = [
    ctypes.c_int,                           # lDeviceId
    ctypes.c_char_p                         # pHeadModel
    ]

# LJS8IF_GetSerialNumber
LJS8IF_GetSerialNumber = mdll.LJS8IF_GetSerialNumber
LJS8IF_GetSerialNumber.restype = ctypes.c_int
LJS8IF_GetSerialNumber.argtypes = [
    ctypes.c_int,                           # lDeviceId
    ctypes.c_char_p                         # pSerialNo
    ]

# LJS8IF_GetAttentionStatus
LJS8IF_GetAttentionStatus = mdll.LJS8IF_GetAttentionStatus
LJS8IF_GetAttentionStatus.restype = ctypes.c_int
LJS8IF_GetAttentionStatus.argtypes = [
    ctypes.c_int,                           # lDeviceId
    ctypes.POINTER(ctypes.c_ushort)         # pwAttentionStatus
    ]

# LJS8IF_Trigger
LJS8IF_Trigger = mdll.LJS8IF_Trigger
LJS8IF_Trigger.restype = ctypes.c_int
LJS8IF_Trigger.argtypes = [
    ctypes.c_int                            # lDeviceId
    ]

# LJS8IF_ClearMemory
LJS8IF_ClearMemory = mdll.LJS8IF_ClearMemory
LJS8IF_ClearMemory.restype = ctypes.c_int
LJS8IF_ClearMemory.argtypes = [
    ctypes.c_int                            # lDeviceId
    ]

# LJS8IF_SetSetting
LJS8IF_SetSetting = mdll.LJS8IF_SetSetting
LJS8IF_SetSetting.restype = ctypes.c_int
LJS8IF_SetSetting.argtypes = [
    ctypes.c_int,                           # lDeviceId
    ctypes.c_ubyte,                         # byDepth
    LJS8IF_TARGET_SETTING,                  # TargetSetting
    ctypes.POINTER(ctypes.c_ubyte),         # pData
    ctypes.c_uint,                          # dwDataSize
    ctypes.POINTER(ctypes.c_uint)           # pdwError
    ]

# LJS8IF_GetSetting
LJS8IF_GetSetting = mdll.LJS8IF_GetSetting
LJS8IF_GetSetting.restype = ctypes.c_int
LJS8IF_GetSetting.argtypes = [
    ctypes.c_int,                           # lDeviceId
    ctypes.c_ubyte,                         # byDepth
    LJS8IF_TARGET_SETTING,                  # TargetSetting
    ctypes.POINTER(ctypes.c_ubyte),         # pData
    ctypes.c_uint                           # dwDataSize
    ]

# LJS8IF_InitializeSetting
LJS8IF_InitializeSetting = mdll.LJS8IF_InitializeSetting
LJS8IF_InitializeSetting.restype = ctypes.c_int
LJS8IF_InitializeSetting.argtypes = [
    ctypes.c_int,                           # lDeviceId
    ctypes.c_ubyte,                         # byDepth
    ctypes.c_ubyte                          # byTarget
    ]

# LJS8IF_ReflectSetting
LJS8IF_ReflectSetting = mdll.LJS8IF_ReflectSetting
LJS8IF_ReflectSetting.restype = ctypes.c_int
LJS8IF_ReflectSetting.argtypes = [
    ctypes.c_int,                           # lDeviceId
    ctypes.c_ubyte,                         # byDepth
    ctypes.POINTER(ctypes.c_uint)           # pdwError
    ]

# LJS8IF_RewriteTemporarySetting
LJS8IF_RewriteTemporarySetting = mdll.LJS8IF_RewriteTemporarySetting
LJS8IF_RewriteTemporarySetting.restype = ctypes.c_int
LJS8IF_RewriteTemporarySetting.argtypes = [
    ctypes.c_int,                           # lDeviceId
    ctypes.c_ubyte                          # byDepth
    ]

# LJS8IF_CheckMemoryAccess
LJS8IF_CheckMemoryAccess = mdll.LJS8IF_CheckMemoryAccess
LJS8IF_CheckMemoryAccess.restype = ctypes.c_int
LJS8IF_CheckMemoryAccess.argtypes = [
    ctypes.c_int,                           # lDeviceId
    ctypes.POINTER(ctypes.c_ubyte)          # pbyBusy
    ]

# LJS8IF_ChangeActiveProgram
LJS8IF_ChangeActiveProgram = mdll.LJS8IF_ChangeActiveProgram
LJS8IF_ChangeActiveProgram.restype = ctypes.c_int
LJS8IF_ChangeActiveProgram.argtypes = [
    ctypes.c_int,                           # lDeviceId
    ctypes.c_ubyte                          # byProgramNo
    ]

# LJS8IF_GetActiveProgram
LJS8IF_GetActiveProgram = mdll.LJS8IF_GetActiveProgram
LJS8IF_GetActiveProgram.restype = ctypes.c_int
LJS8IF_GetActiveProgram.argtypes = [
    ctypes.c_int,                           # lDeviceId
    ctypes.POINTER(ctypes.c_ubyte)          # pbyProgramNo
    ]

# LJS8IF_GetHeightImageSimpleArray
LJS8IF_GetHeightImageSimpleArray = mdll.LJS8IF_GetHeightImageSimpleArray
LJS8IF_GetHeightImageSimpleArray.restype = ctypes.c_int
LJS8IF_GetHeightImageSimpleArray.argtypes = [
    ctypes.c_int,                                              # lDeviceId
    ctypes.POINTER(LJS8IF_GET_HEIGHT_IMAGE_PROFILE_REQUEST),   # pReq
    ctypes.c_ubyte,                                    # byUsePCImageFilter
    ctypes.POINTER(LJS8IF_GET_HEIGHT_IMAGE_PROFILE_RESPONSE),  # pRsp
    ctypes.POINTER(LJS8IF_HEIGHT_IMAGE_INFO),          # pHeightImageInfo
    ctypes.POINTER(LJS8IF_PROFILE_HEADER),             # pProfileHeaderArray
    ctypes.POINTER(ctypes.c_ushort),                   # pHeightProfileArray
    ctypes.POINTER(ctypes.c_ubyte)                     # pLuminanceProfileArray
    ]

# LJS8IF_InitializeHighSpeedDataCommunicationSimpleArray
LJS8IF_InitializeHighSpeedDataCommunicationSimpleArray \
    = mdll.LJS8IF_InitializeHighSpeedDataCommunicationSimpleArray
LJS8IF_InitializeHighSpeedDataCommunicationSimpleArray.restype = ctypes.c_int
LJS8IF_InitializeHighSpeedDataCommunicationSimpleArray.argtypes = [
    ctypes.c_int,                               # lDeviceId
    ctypes.POINTER(LJS8IF_ETHERNET_CONFIG),     # pEthernetConfig
    ctypes.c_ushort,                            # wHighSpeedPortNo
    LJS8IF_CALLBACK_SIMPLE_ARRAY,               # pCallBackSimpleArray
    ctypes.c_uint                               # dwThreadId
    ]

# LJS8IF_PreStartHighSpeedDataCommunication
LJS8IF_PreStartHighSpeedDataCommunication \
    = mdll.LJS8IF_PreStartHighSpeedDataCommunication
LJS8IF_PreStartHighSpeedDataCommunication.restype = ctypes.c_int
LJS8IF_PreStartHighSpeedDataCommunication.argtypes = [
    ctypes.c_int,                                       # lDeviceId
    ctypes.POINTER(LJS8IF_HIGH_SPEED_PRE_START_REQ),    # pReq
    ctypes.c_ubyte,                                     # byUsePCImageFilter
    ctypes.POINTER(LJS8IF_HEIGHT_IMAGE_INFO)       # pHeightImageInfo
    ]

# LJS8IF_StartHighSpeedDataCommunication
LJS8IF_StartHighSpeedDataCommunication \
    = mdll.LJS8IF_StartHighSpeedDataCommunication
LJS8IF_StartHighSpeedDataCommunication.restype = ctypes.c_int
LJS8IF_StartHighSpeedDataCommunication.argtypes = [
    ctypes.c_int                            # lDeviceId
    ]

# LJS8IF_StopHighSpeedDataCommunication
LJS8IF_StopHighSpeedDataCommunication \
    = mdll.LJS8IF_StopHighSpeedDataCommunication
LJS8IF_StopHighSpeedDataCommunication.restype = ctypes.c_int
LJS8IF_StopHighSpeedDataCommunication.argtypes = [
    ctypes.c_int                            # lDeviceId
    ]

# LJS8IF_FinalizeHighSpeedDataCommunication
LJS8IF_FinalizeHighSpeedDataCommunication \
    = mdll.LJS8IF_FinalizeHighSpeedDataCommunication
LJS8IF_FinalizeHighSpeedDataCommunication.restype = ctypes.c_int
LJS8IF_FinalizeHighSpeedDataCommunication.argtypes = [
    ctypes.c_int                            # lDeviceId
    ]
