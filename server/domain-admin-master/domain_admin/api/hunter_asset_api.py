# -*- coding: utf-8 -*-
"""
hunter_asset_api.py
"""
import io
import csv
from flask import request, g

from domain_admin.enums.role_enum import RoleEnum
from domain_admin.service import auth_service, hunter_asset_service
from domain_admin.utils.flask_ext.app_exception import AppException

@auth_service.permission(role=RoleEnum.USER)
def get_classified_assets():
    """
    获取资产分类列表
    """
    keyword = request.json.get('keyword', '')
    page = request.json.get('page', 1)
    size = request.json.get('size', 50)
    
    return hunter_asset_service.get_classified_assets(keyword, page, size)


@auth_service.permission(role=RoleEnum.USER)
def update_classified_asset_status():
    """
    更新资产渗透状态
    Swagger:
      path: /api/updateClassifiedAssetStatus
      method: POST
      body:
        asset_id: int
        is_completed: bool
      response:
        asset_id: int
        penetration_status: completed|pending
    """
    body = request.json or {}
    asset_id = body.get("asset_id")
    is_completed = body.get("is_completed")
    if asset_id is None:
        raise AppException("缺少必要参数: asset_id")
    if is_completed is None:
        raise AppException("缺少必要参数: is_completed")
    return hunter_asset_service.update_asset_penetration_status(asset_id, is_completed)


@auth_service.permission(role=RoleEnum.USER)
def update_classified_asset_remark():
    """
    更新资产渗透备注
    Swagger:
      path: /api/updateClassifiedAssetRemark
      method: POST
      body:
        asset_id: int
        remark: string
      response:
        asset_id: int
        penetration_remark: string
    """
    body = request.json or {}
    asset_id = body.get("asset_id")
    if asset_id is None:
        raise AppException("缺少必要参数: asset_id")
    remark = body.get("remark", "")
    return hunter_asset_service.update_asset_penetration_remark(asset_id, remark)

@auth_service.permission(role=RoleEnum.USER)
def trigger_full_asset_pipeline():
    """
    一键触发自动化资产流水线 (Hunter采集 -> 入库 -> DeepSeek分类)
    """
    icp_keyword = request.json.get('icp_keyword')
    limit = request.json.get('limit', 100)
    
    if not icp_keyword:
        raise AppException('缺少必要参数: icp_keyword')
        
    current_user_id = g.user_id
    hunter_asset_service.trigger_full_asset_pipeline(icp_keyword, limit, current_user_id)
    return {"msg": f"自动化流水线已下发，正在处理备案主体：{icp_keyword}，请查看异步任务日志"}

@auth_service.permission(role=RoleEnum.USER)
def trigger_asset_classification():
    """
    手动触发资产智能分类任务
    """
    current_user_id = g.user_id
    hunter_asset_service.trigger_asset_classification(current_user_id)
    return {"msg": "任务已下发后台执行，请查看异步任务日志"}

@auth_service.permission(role=RoleEnum.USER)
def import_hunter_asset_csv():
    """
    导入 Hunter 资产 CSV
    """
    file = request.files.get('file')
    if not file:
        raise AppException('请上传文件')

    if not file.filename.endswith('.csv'):
        raise AppException('只支持导入 .csv 文件')

    try:
        # 读取文件内容，支持 utf-8 和 utf-8-sig
        content = file.read().decode('utf-8-sig')
        file_stream = io.StringIO(content)
        
        # 获取当前用户ID
        current_user_id = g.user_id
        
        # 调用服务层进行处理
        result = hunter_asset_service.import_csv_data(file_stream, current_user_id)
        return result
    except Exception as e:
        raise AppException(str(e))
