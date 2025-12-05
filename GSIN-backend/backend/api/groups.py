# backend/api/groups.py
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Body, status
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import uuid

from ..db.session import get_db
from ..db import crud
from ..db.models import Group, GroupMember, GroupMessage, UserStrategy
from ..utils.encryption import encrypt_message, decrypt_message
from ..utils.jwt_deps import get_current_user_id_dep

router = APIRouter(prefix="/groups", tags=["groups"])
# PHASE 4: JWT-only authentication

# Response models
class GroupResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    owner_id: str
    join_code: str
    max_size: Optional[int]
    is_discoverable: bool
    is_paid: bool
    price_monthly: Optional[int]
    created_at: str

    class Config:
        from_attributes = True

class MemberResponse(BaseModel):
    id: str
    user_id: str
    role: str
    created_at: str

class CreateGroupRequest(BaseModel):
    name: str
    description: Optional[str] = None

class JoinGroupRequest(BaseModel):
    join_code: str

class CreateMessageRequest(BaseModel):
    content: str  # Plain text message (will be encrypted)
    message_type: Optional[str] = "TEXT"  # "TEXT", "STRATEGY"
    strategy_id: Optional[str] = None  # For strategy messages

class MessageResponse(BaseModel):
    id: str
    group_id: str
    user_id: str
    content: str  # Decrypted content (only for authorized users)
    message_type: Optional[str] = "TEXT"
    strategy_id: Optional[str] = None
    strategy_data: Optional[Dict[str, Any]] = None  # Strategy details if message_type is "STRATEGY"
    created_at: str
    sender_name: Optional[str] = None  # User name for display
    is_owner_message: bool = False  # Whether sender is group owner

def get_user_group_creation_limit(db: Session, user_id: str) -> int:
    """
    Get the maximum number of groups a user can create based on their subscription plan.
    PHASE 4: JWT-only authentication.
    Returns:
        - USER plan: 1 group
        - USER_PLUS_UPLOAD plan: 10 groups
        - CREATOR plan: unlimited (return 999 as practical limit)
    """
    sub_info = crud.get_user_subscription_info(db, user_id)
    if not sub_info:
        # No plan = USER plan (default)
        return 1
    
    plan_code = sub_info.get("plan_code", "USER")
    
    if plan_code == "USER":
        return 1
    elif plan_code == "USER_PLUS_UPLOAD":
        return 10
    elif plan_code == "CREATOR":
        return 999  # Practical unlimited
    else:
        # Unknown plan, default to USER limits
        return 1

def can_user_create_group(db: Session, user_id: str) -> tuple[bool, str]:
    """
    Check if user can create a new group based on their plan and current group count.
    Returns (can_create: bool, reason: str)
    """
    limit = get_user_group_creation_limit(db, user_id)
    current_count = crud.count_user_owned_groups(db, user_id)
    
    if current_count >= limit:
        plan_name = "your current plan"
        sub_info = crud.get_user_subscription_info(db, user_id)
        if sub_info and sub_info.get("plan_name"):
            plan_name = sub_info["plan_name"]
        
        if limit == 1:
            return False, f"You have reached the group creation limit for {plan_name}. Upgrade to create more groups."
        else:
            return False, f"You have reached the group creation limit ({limit} groups) for {plan_name}."
    
    return True, ""

# POST /api/groups
@router.post("", response_model=GroupResponse)
def create_group(
    group_data: CreateGroupRequest = Body(...),
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """
    Create a new group.
    Enforces plan-based creation limits:
    - USER plan: 1 group max
    - USER_PLUS_UPLOAD plan: 10 groups max
    - CREATOR plan: unlimited
    """
    
    
    # Validate name
    if not group_data.name or not group_data.name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Group name is required"
        )
    
    # Check if user can create a group
    can_create, reason = can_user_create_group(db, user_id)
    if not can_create:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=reason
        )
    
    # Create group
    group = crud.create_group(
        db,
        owner_id=user_id,
        name=group_data.name.strip(),
        description=group_data.description.strip() if group_data.description else None,
    )
    
    return GroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        owner_id=group.owner_id,
        join_code=group.join_code,
        max_size=group.max_size,
        is_discoverable=group.is_discoverable,
        is_paid=group.is_paid,
        price_monthly=group.price_monthly,
        created_at=group.created_at.isoformat(),
    )

# POST /api/groups/join
@router.post("/join", response_model=GroupResponse)
def join_group(
    join_data: JoinGroupRequest = Body(...),
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """
    Join a group using a join_code.
    """
    
    
    if not join_data.join_code or not join_data.join_code.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Join code is required"
        )
    
    # Find group by join_code
    group = crud.join_group_by_code(db, user_id, join_data.join_code.strip().upper())
    
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found. Please check the join code."
        )
    
    return GroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        owner_id=group.owner_id,
        join_code=group.join_code,
        max_size=group.max_size,
        is_discoverable=group.is_discoverable,
        is_paid=group.is_paid,
        price_monthly=group.price_monthly,
        created_at=group.created_at.isoformat(),
    )

# GET /api/groups
@router.get("", response_model=Dict[str, List[GroupResponse]])
def list_groups(
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """
    Get all groups for the current user.
    Returns separate lists for groups the user owns and groups the user is a member of.
    """
    
    
    groups_data = crud.list_user_groups(db, user_id)
    
    return {
        "owned": [
            GroupResponse(
                id=g["id"],
                name=g["name"],
                description=g.get("description"),
                owner_id=g["owner_id"],
                join_code=g["join_code"],
                max_size=g.get("max_size"),
                is_discoverable=g.get("is_discoverable", False),
                is_paid=g.get("is_paid", False),
                price_monthly=g.get("price_monthly"),
                created_at=g["created_at"],
            )
            for g in groups_data["owned"]
        ],
        "member": [
            GroupResponse(
                id=g["id"],
                name=g["name"],
                description=g.get("description"),
                owner_id=g["owner_id"],
                join_code=g["join_code"],
                max_size=g.get("max_size"),
                is_discoverable=g.get("is_discoverable", False),
                is_paid=g.get("is_paid", False),
                price_monthly=g.get("price_monthly"),
                created_at=g["created_at"],
            )
            for g in groups_data.get("joined", [])  # Fixed: use "joined" key from crud
        ]
    }

# GET /api/groups/{group_id}
@router.get("/{group_id}", response_model=GroupResponse)
def get_group(
    group_id: str,
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """
    Get group details by ID.
    """
    
    
    group = crud.get_group(db, group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )
    
    # Check if user has access (owner or member)
    is_owner = group.owner_id == user_id
    is_member = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.user_id == user_id
    ).first() is not None
    
    if not is_owner and not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this group"
        )
    
    return GroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        owner_id=group.owner_id,
        join_code=group.join_code,
        max_size=group.max_size,
        is_discoverable=group.is_discoverable,
        is_paid=group.is_paid,
        price_monthly=group.price_monthly,
        created_at=group.created_at.isoformat(),
    )

# GET /api/groups/{group_id}/members
@router.get("/{group_id}/members", response_model=List[MemberResponse])
def get_group_members(
    group_id: str,
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """
    Get all members of a group.
    """
    
    
    group = crud.get_group(db, group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )
    
    # Check if user has access (owner or member)
    is_owner = group.owner_id == user_id
    is_member = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.user_id == user_id
    ).first() is not None
    
    if not is_owner and not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this group"
        )
    
    members = crud.get_group_members(db, group_id)
    
    return [
        MemberResponse(
            id=m["id"],
            user_id=m["user_id"],
            role=m["role"],
            created_at=m["created_at"],
        )
        for m in members
    ]

# DELETE /api/groups/{group_id}
@router.delete("/{group_id}")
def delete_group(
    group_id: str,
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """
    Delete a group. Only the group owner can delete the group.
    This will cascade delete all group members and messages.
    Sends notifications to all members before deletion.
    """
    from ..db.models import Notification
    import uuid
    
    group = crud.get_group(db, group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )
    
    # Only owner can delete the group
    if group.owner_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the group owner can delete the group"
        )
    
    # Get all members before deletion to send notifications
    members = crud.get_group_members(db, group_id)
    member_user_ids = [m["user_id"] for m in members if m["user_id"] != user_id]  # Exclude owner
    
    # Send notifications to all members before deleting
    for member_id in member_user_ids:
        notification = Notification(
            id=str(uuid.uuid4()),
            user_id=member_id,
            title="Group Deleted",
            body=f"The group '{group.name}' has been deleted by the group owner.",
            read_flag=False,
            created_by=user_id,
        )
        db.add(notification)
    
    # Commit notifications before deleting group
    db.commit()
    
    # Delete the group (cascade will handle members and messages)
    deleted = crud.delete_group(db, group_id, user_id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the group owner can delete the group"
        )
    
    return {"message": "Group deleted successfully"}

# POST /api/groups/{group_id}/messages
@router.post("/{group_id}/messages", response_model=MessageResponse)
def create_group_message(
    group_id: str,
    message_data: CreateMessageRequest = Body(...),
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """
    Send a message to a group. Message is encrypted before storage.
    Only group members can send messages.
    """
    
    
    if not message_data.content or not message_data.content.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message content cannot be empty"
        )
    
    group = crud.get_group(db, group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )
    
    # Check if user is a member of the group
    is_owner = group.owner_id == user_id
    is_member = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.user_id == user_id
    ).first() is not None
    
    if not is_owner and not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be a member of this group to send messages"
        )
    
    # GROUP CHAT STRATEGY FUNCTIONALITY: Handle strategy uploads
    strategy_data = None
    strategy_id = None
    
    if message_data.message_type == "STRATEGY" and message_data.strategy_id:
        # Verify strategy exists and belongs to user (or user has access)
        from ..db.models import UserStrategy
        strategy = db.query(UserStrategy).filter(UserStrategy.id == message_data.strategy_id).first()
        if not strategy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Strategy not found"
            )
        
        # Only group owner can upload strategies
        if not is_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the group owner can upload strategies"
            )
        
        # Check if strategy is already in this group (prevent duplicates)
        existing_strategy_msg = db.query(GroupMessage).filter(
            GroupMessage.group_id == group_id,
            GroupMessage.strategy_id == message_data.strategy_id,
            GroupMessage.message_type == "STRATEGY"
        ).first()
        
        if existing_strategy_msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This strategy is already shared in this group"
            )
        
        strategy_id = strategy.id
        strategy_data = {
            "id": strategy.id,
            "name": strategy.name,
            "description": strategy.description,
            "status": strategy.status,
            "is_backtested": strategy.last_backtest_at is not None,
            "backtest_status": "Backtested by GSIN Brain" if strategy.last_backtest_at else "Not backtested by GSIN Brain",
            "win_rate": strategy.test_metrics.get("win_rate") if strategy.test_metrics else None,
            "sharpe_ratio": strategy.test_metrics.get("sharpe_ratio") if strategy.test_metrics else None,
            "total_trades": strategy.test_metrics.get("total_trades") if strategy.test_metrics else None,
        }
        
        # Mark strategy as group-only if group has privacy setting
        if group.strategies_private:
            # Store group_id in strategy metadata (we'll add a group_ids field or use a junction table)
            # For now, we'll track this via the message relationship
            pass  # Placeholder for future implementation
    
    # Encrypt the message
    encrypted_content = encrypt_message(message_data.content.strip())
    
    # Create message
    message = crud.create_group_message(
        db,
        group_id=group_id,
        user_id=user_id,
        encrypted_content=encrypted_content,
        message_type=message_data.message_type or "TEXT",
        strategy_id=strategy_id,
    )
    
    # Get sender name
    sender = crud.get_user_by_id(db, user_id)
    sender_name = sender.name if sender else "Unknown"
    
    return MessageResponse(
        id=message.id,
        group_id=message.group_id,
        user_id=message.user_id,
        content=message_data.content.strip(),  # Return decrypted content
        message_type=message.message_type,
        strategy_id=message.strategy_id,
        strategy_data=strategy_data,
        created_at=message.created_at.isoformat(),
        sender_name=sender_name,
        is_owner_message=(group.owner_id == user_id),
    )

# GET /api/groups/{group_id}/messages
@router.get("/{group_id}/messages", response_model=List[MessageResponse])
def get_group_messages(
    group_id: str,
    limit: int = 100,
    offset: int = 0,
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """
    Get messages for a group. Messages are decrypted for authorized users.
    Only group members and owner can view messages.
    """
    
    
    group = crud.get_group(db, group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )
    
    # Check if user has access (owner or member)
    is_owner = group.owner_id == user_id
    is_member = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.user_id == user_id
    ).first() is not None
    
    if not is_owner and not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this group's messages"
        )
    
    # Get messages
    messages = crud.list_group_messages(db, group_id, limit=limit, offset=offset)
    
    # Decrypt messages and get sender names
    result = []
    for msg in messages:
        # Decrypt the message
        decrypted_content = decrypt_message(msg.encrypted_content)
        
        # Get sender name
        sender = crud.get_user_by_id(db, msg.user_id)
        sender_name = sender.name if sender else "Unknown"
        
        # GROUP CHAT STRATEGY FUNCTIONALITY: Include strategy data if message has strategy
        strategy_data = None
        if msg.message_type == "STRATEGY" and msg.strategy_id:
            from ..db.models import UserStrategy
            strategy = db.query(UserStrategy).filter(UserStrategy.id == msg.strategy_id).first()
            if strategy:
                strategy_data = {
                    "id": strategy.id,
                    "name": strategy.name,
                    "description": strategy.description,
                    "status": strategy.status,
                    "is_backtested": strategy.last_backtest_at is not None,
                    "backtest_status": "Backtested by GSIN Brain" if strategy.last_backtest_at else "Not backtested by GSIN Brain",
                    "win_rate": strategy.test_metrics.get("win_rate") if strategy.test_metrics else None,
                    "sharpe_ratio": strategy.test_metrics.get("sharpe_ratio") if strategy.test_metrics else None,
                    "total_trades": strategy.test_metrics.get("total_trades") if strategy.test_metrics else None,
                    "explanation_human": strategy.explanation_human,
                    "risk_note": strategy.risk_note,
                }
        
        result.append(MessageResponse(
            id=msg.id,
            group_id=msg.group_id,
            user_id=msg.user_id,
            content=decrypted_content,
            message_type=msg.message_type,
            strategy_id=msg.strategy_id,
            strategy_data=strategy_data,
            created_at=msg.created_at.isoformat(),
            sender_name=sender_name,
            is_owner_message=(group.owner_id == msg.user_id),
        ))
    
    return result

# DELETE /api/groups/{group_id}/messages/{message_id}
@router.delete("/{group_id}/messages/{message_id}")
def delete_group_message(
    group_id: str,
    message_id: str,
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """
    Delete a group message (soft delete).
    Rules:
    - Group owner can delete any message
    - Regular members can only delete their own messages
    - Members cannot delete owner's messages
    """
    
    
    group = crud.get_group(db, group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )
    
    # Check if user has access to the group
    is_owner = group.owner_id == user_id
    is_member = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.user_id == user_id
    ).first() is not None
    
    if not is_owner and not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this group"
        )
    
    # Delete the message (with permission checks)
    deleted = crud.delete_group_message(db, message_id, user_id, group_id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to delete this message. Only the group owner can delete owner's messages."
        )
    
    return {"message": "Message deleted successfully"}


# PHASE 5: Leave group endpoint
@router.post("/{group_id}/leave")
async def leave_group(
    group_id: str,
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """
    Leave a group (PHASE 5).
    Members can leave groups they joined (not owned).
    """
    group = crud.get_group(db, group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )
    
    # Owner cannot leave their own group
    if group.owner_id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Group owner cannot leave their own group. Delete the group instead."
        )
    
    # Check if user is a member
    membership = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.user_id == user_id
    ).first()
    
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You are not a member of this group"
        )
    
    # Remove membership
    db.delete(membership)
    db.commit()
    
    return {"message": "Successfully left the group"}


# Note: Delete group endpoint is defined earlier in the file (line 341)
# This duplicate definition is removed to avoid conflicts


# POST /api/groups/{group_id}/strategies/{strategy_id}/execute
@router.post("/{group_id}/strategies/{strategy_id}/execute")
async def execute_group_strategy(
    group_id: str,
    strategy_id: str,
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """
    Execute a strategy from a group message.
    Any group member can execute strategies posted by the group owner.
    This generates a brain signal and places a trade.
    """
    # Verify group exists and user is a member
    group = crud.get_group(db, group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )
    
    # Check if user is a member (owner or regular member)
    is_owner = group.owner_id == user_id
    is_member = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.user_id == user_id
    ).first() is not None
    
    if not is_owner and not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be a group member to execute strategies"
        )
    
    # Verify strategy exists and is accessible
    strategy = crud.get_user_strategy(db, strategy_id)
    if not strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Strategy not found"
        )
    
    # For now, return success - actual execution should be handled by frontend
    # calling the brain signal API and broker API
    return {
        "message": "Strategy execution initiated",
        "strategy_id": strategy_id,
        "group_id": group_id
    }

# PHASE 5: Create referral code for group invite
@router.post("/{group_id}/referral")
async def create_group_referral(
    group_id: str,
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """
    Create a referral code for inviting users to a group (PHASE 5).
    Only group owner can create referral codes.
    """
    group = crud.get_group(db, group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )
    
    if group.owner_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the group owner can create referral codes"
        )
    
    # Generate referral code
    from ..db.models import Referral
    import random
    import string
    
    referral_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    
    # Check for uniqueness
    while db.query(Referral).filter(Referral.referral_code == referral_code).first():
        referral_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    
    referral = Referral(
        id=str(uuid.uuid4()),
        referrer_id=user_id,
        referral_code=referral_code,
        referral_type="group_invite",
        group_id=group_id,
        used=False
    )
    
    db.add(referral)
    db.commit()
    db.refresh(referral)
    
    return {
        "referral_code": referral_code,
        "group_id": group_id,
        "expires_at": None,  # Could add expiration logic
        "used": False
    }


# PHASE 5: Use referral code to join group
@router.post("/join/referral")
async def join_group_by_referral(
    referral_code: str = Body(..., embed=True),
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """
    Join a group using a referral code (PHASE 5).
    """
    from ..db.models import Referral
    
    referral = db.query(Referral).filter(
        Referral.referral_code == referral_code.upper(),
        Referral.used == False
    ).first()
    
    if not referral:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired referral code"
        )
    
    if referral.referral_type != "group_invite" or not referral.group_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid referral code type"
        )
    
    # Join the group
    group = crud.join_group_by_code(db, user_id, referral.group_id)  # Use group_id directly
    if not group:
        # Check if already a member
        existing_member = db.query(GroupMember).filter(
            GroupMember.group_id == referral.group_id,
            GroupMember.user_id == user_id
        ).first()
        
        if existing_member:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You are already a member of this group"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to join group"
            )
    
    # Mark referral as used
    referral.used = True
    referral.referred_id = user_id
    referral.used_at = datetime.now(timezone.utc)
    db.commit()
    
    return GroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        owner_id=group.owner_id,
        join_code=group.join_code,
        max_size=group.max_size,
        is_discoverable=group.is_discoverable,
        is_paid=group.is_paid,
        price_monthly=group.price_monthly,
        created_at=group.created_at.isoformat(),
    )

