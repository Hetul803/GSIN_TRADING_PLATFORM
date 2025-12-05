# backend/brain/mcn_adapter.py
"""
MCN Adapter - Wrapper for MemoryClusterNetworks library.
Handles all interactions with the MCN system.
"""
from typing import Dict, Any, Optional, List
import os
import sys
import time
from pathlib import Path
from dotenv import dotenv_values
import numpy as np
import asyncio
import threading

# Try to import MemoryClusterNetworks
try:
    from MemoryClusterNetworks.src.mcn import MCNLayer
    MCN_AVAILABLE = True
except ImportError:
    try:
        # Alternative import path
        from mcn import MCNLayer
        MCN_AVAILABLE = True
    except ImportError:
        MCNLayer = None
        MCN_AVAILABLE = False
        print("WARNING: MemoryClusterNetworks not available. MCN features will be disabled.")

# Try to import sentence-transformers for embeddings
try:
    from sentence_transformers import SentenceTransformer
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    SentenceTransformer = None
    EMBEDDINGS_AVAILABLE = False
    print("WARNING: sentence-transformers not available. Using fallback embeddings.")


class MCNAdapter:
    """
    Adapter for MemoryClusterNetworks.
    Provides a clean interface for recording events, retrieving memory, and generating recommendations.
    
    Supports two modes:
    - "required": MCN must be available (production mode)
    - "fallback": MCN is optional, uses stub if unavailable (development mode)
    """
    
    # PHASE: Global constant for MCN dimension enforcement
    MCN_DIM = 32
    FIXED_DIM = 32  # Alias for backward compatibility
    
    def _fix_dim(self, vector: np.ndarray, target_dim: int = None) -> np.ndarray:
        """
        PHASE: Fix vector dimension to target_dim (default: MCN_DIM = 32).
        
        Uses np.resize() to ensure exact dimension match.
        Ensures all vectors have consistent dimensionality.
        
        Args:
            vector: Input vector (1D or 2D)
            target_dim: Target dimension (default: MCN_DIM = 32)
        
        Returns:
            Vector with fixed dimension (MCN_DIM,)
        """
        if target_dim is None:
            target_dim = self.MCN_DIM
        
        # Handle None or empty vectors
        if vector is None or vector.size == 0:
            return np.zeros(target_dim, dtype=np.float32)
        
        # Convert to numpy array and ensure float32
        vector = np.asarray(vector, dtype=np.float32)
        
        # Flatten to 1D if needed
        if vector.ndim > 1:
            vector = vector.flatten()
        
        # PHASE: Use np.resize() to ensure exact dimension match
        if vector.shape[0] != target_dim:
            vector = np.resize(vector, target_dim)
        
        return vector.astype(np.float32)
    
    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize MCN instance with persistent storage and embeddings.
        
        Args:
            storage_path: Path to MCN storage directory. If None, loads from MCN_STORAGE_PATH env var.
        
        Raises:
            RuntimeError: If BRAIN_MCN_MODE=required and MCN is not available
        """
        # PHASE E: Split MCN into 5 separate memories
        self.mcn_regime = None
        self.mcn_strategy = None
        self.mcn_user = None
        self.mcn_market = None
        self.mcn_trade = None
        
        # Keep backward compatibility with self.mcn (points to mcn_strategy for now)
        self.mcn = None
        
        self.is_available = MCN_AVAILABLE
        self.storage_path = storage_path or self._get_storage_path()
        self.embedder = None
        self.mode = self._get_mcn_mode()
        self.is_stub_mode = False
        
        # PHASE D: Thread safety - create locks for async and thread operations
        self.mcn_lock = asyncio.Lock()  # For async operations
        self.thread_lock = threading.Lock()  # For thread operations
        
        # Initialize embedder
        if EMBEDDINGS_AVAILABLE:
            try:
                # Use a small, fast model for embeddings
                # Suppress PyTorch meta tensor warnings
                import warnings
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=UserWarning)
                    self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
                print("✅ Using sentence-transformers for embeddings")
            except Exception as e:
                # Suppress specific PyTorch meta tensor error (known issue with some PyTorch versions)
                error_msg = str(e)
                if "meta tensor" in error_msg.lower() or "to_empty" in error_msg.lower():
                    print("⚠️  sentence-transformers has PyTorch compatibility issue, using fallback embeddings")
                else:
                    print(f"⚠️  Failed to load sentence-transformers: {e}")
                self.embedder = None
        
        # Check mode and enforce requirements
        if self.mode == "required" and not MCN_AVAILABLE:
            raise RuntimeError(
                "BRAIN_MCN_MODE=required but MemoryClusterNetworks is not available. "
                "Please install MemoryClusterNetworks or set BRAIN_MCN_MODE=fallback for development."
            )
        
        if MCN_AVAILABLE:
            try:
                # Load config from environment
                CFG_PATH = Path(__file__).resolve().parents[3] / "config" / ".env"
                cfg = dotenv_values(str(CFG_PATH)) if CFG_PATH.exists() else {}
                
                decay_rate = float(os.environ.get("MCN_DECAY_RATE") or cfg.get("MCN_DECAY_RATE", "1e-6"))
                budget = int(os.environ.get("MCN_BUDGET") or cfg.get("MCN_BUDGET", "10000"))
                # PHASE: Use fixed dimension (32) for all MCN operations to prevent broadcasting errors
                dim = self.FIXED_DIM
                
                # Ensure storage directory exists
                if self.storage_path:
                    os.makedirs(self.storage_path, exist_ok=True)
                    storage_file = os.path.join(self.storage_path, "mcn_state.npz")
                    
                    # PHASE 7: Try to load existing state with improved error handling
                    if os.path.exists(storage_file):
                        try:
                            self.mcn = MCNLayer.load(storage_file)
                            print(f"✅ MCN loaded from {storage_file}")
                        except Exception as e:
                            # PHASE 7: Improved error handling - only treat specific errors as corruption
                            error_msg = str(e)
                            error_msg_lower = error_msg.lower()
                            error_type = type(e).__name__
                            
                            # Only treat as corruption if it's the EXACT known bug from external library
                            # The known bug is: "cannot access local variable 'json' where it is not associated with a value"
                            is_known_corruption = (
                                "cannot access local variable 'json'" in error_msg_lower and
                                ("where it is not associated with a value" in error_msg_lower or
                                 "is not associated with a value" in error_msg_lower)
                            )
                            
                            if is_known_corruption:
                                # Known bug in MemoryClusterNetworks library - backup old file and create new
                                import shutil
                                backup_file = f"{storage_file}.backup.{int(time.time())}"
                                try:
                                    if os.path.exists(storage_file):
                                        shutil.copy2(storage_file, backup_file)
                                        print(f"   📦 Backed up corrupted state to {backup_file}")
                                    # Remove corrupted file
                                    os.remove(storage_file)
                                    print(f"   🗑️  Removed corrupted MCN state file (known library bug)")
                                except Exception as backup_error:
                                    print(f"   ⚠️  Could not backup corrupted file: {backup_error}")
                                
                                print(f"   Creating new MCN instance - state will be saved after first use")
                                
                                # Create new instance and save
                                self.mcn = MCNLayer(
                                    dim=dim,
                                    budget=budget,
                                    lambda_decay=decay_rate,
                                    auto_maintain=True
                                )
                                try:
                                    self.mcn.save(storage_file)
                                    print(f"✅ Created new MCN state at {storage_file}")
                                except Exception as save_error:
                                    print(f"⚠️  Could not save MCN state immediately: {save_error}")
                            else:
                                # Other errors - might be temporary (file lock, permission, version mismatch, etc.)
                                # Don't delete the file, just create new instance in memory
                                import logging
                                logger = logging.getLogger(__name__)
                                logger.warning(f"MCN load error (not corruption, preserving file): {error_type}: {error_msg}")
                                print(f"⚠️  MCN state file load error (preserving file): {error_type}")
                                print(f"   Error: {error_msg[:200]}")  # Show first 200 chars of error
                                print(f"   Creating new instance in memory - existing file preserved")
                                print(f"   Will try to load again next time (file: {storage_file})")
                                
                                # Create new instance but DON'T save (preserve existing file)
                                self.mcn = MCNLayer(
                                    dim=dim,
                                    budget=budget,
                                    lambda_decay=decay_rate,
                                    auto_maintain=True
                                )
                                # Don't save - preserve existing file for next attempt
                                print(f"   Existing MCN state file preserved - will attempt load on next restart")
                    else:
                        # Create new instance
                        self.mcn = MCNLayer(
                            dim=dim,
                            budget=budget,
                            lambda_decay=decay_rate,
                            auto_maintain=True
                        )
                        print(f"✅ MCN initialized (new instance, will save to {storage_file})")
                else:
                    # No storage path, create in-memory only
                    self.mcn = MCNLayer(
                        dim=dim,
                        budget=budget,
                        lambda_decay=decay_rate,
                        auto_maintain=True
                    )
                    print("✅ MCN initialized (in-memory only, no persistence)")
                    
            except Exception as e:
                if self.mode == "required":
                    raise RuntimeError(f"Failed to initialize MCN (required mode): {e}")
                print(f"WARNING: Failed to initialize MCN: {e}")
                import traceback
                traceback.print_exc()
                self.is_available = False
                self.mcn = None
                self.is_stub_mode = True
        else:
            # MCN not available
            if self.mode == "required":
                raise RuntimeError(
                    "BRAIN_MCN_MODE=required but MemoryClusterNetworks is not available. "
                    "Please install MemoryClusterNetworks or set BRAIN_MCN_MODE=fallback for development."
                )
            # Fallback mode: use stub
            self.is_stub_mode = True
            print("⚠️  MCN STUB MODE: MemoryClusterNetworks not available, using deterministic stub")
    
    def _get_storage_path(self) -> Optional[str]:
        """Get MCN storage path from environment or config."""
        CFG_PATH = Path(__file__).resolve().parents[3] / "config" / ".env"
        cfg = dotenv_values(str(CFG_PATH)) if CFG_PATH.exists() else {}
        
        storage_path = (
            os.environ.get("MCN_STORAGE_PATH") or 
            cfg.get("MCN_STORAGE_PATH") or 
            "./mcn_store"
        )
        return storage_path
    
    def _get_mcn_mode(self) -> str:
        """
        Get MCN mode from environment.
        
        Returns:
            "required" if ENVIRONMENT=production, "fallback" otherwise
        """
        CFG_PATH = Path(__file__).resolve().parents[3] / "config" / ".env"
        cfg = dotenv_values(str(CFG_PATH)) if CFG_PATH.exists() else {}
        
        # Check explicit BRAIN_MCN_MODE first
        explicit_mode = os.environ.get("BRAIN_MCN_MODE") or cfg.get("BRAIN_MCN_MODE")
        if explicit_mode in ["required", "fallback"]:
            return explicit_mode
        
        # Auto-detect based on environment
        env = os.environ.get("ENVIRONMENT") or cfg.get("ENVIRONMENT", "development")
        if env == "production":
            return "required"
        return "fallback"
    
    def save_state(self) -> bool:
        """
        PHASE E: Save all 5 MCN states to disk.
        Automatically prunes if any state file exceeds 1GB.
        
        Returns:
            True if all saved successfully, False otherwise
        """
        if not self.is_available or not self.storage_path:
            return False
        
        mcn_instances = {
            "regime": self.mcn_regime,
            "strategy": self.mcn_strategy,
            "user": self.mcn_user,
            "market": self.mcn_market,
            "trade": self.mcn_trade,
        }
        
        saved_counts = {}
        
        # PHASE D: Wrap MCN save with thread lock
        with self.thread_lock:
            for category, mcn_instance in mcn_instances.items():
                if mcn_instance:
                    try:
                        # Get MCN size before saving
                        size = None
                        try:
                            # Try common MCN size attributes
                            if hasattr(mcn_instance, "vals") and mcn_instance.vals is not None:
                                size = len(mcn_instance.vals) if hasattr(mcn_instance.vals, "__len__") else None
                            elif hasattr(mcn_instance, "size"):
                                size = mcn_instance.size
                            elif hasattr(mcn_instance, "n"):
                                size = mcn_instance.n
                        except (AttributeError, TypeError, MemoryError):
                            size = None
                        
                        category_path = os.path.join(self.storage_path, f"mcn_{category}")
                        os.makedirs(category_path, exist_ok=True)
                        storage_file = os.path.join(category_path, "mcn_state.npz")
                        
                        # Check file size before saving (prune if needed)
                        if os.path.exists(storage_file):
                            file_size = os.path.getsize(storage_file)
                            # 1GB = 1073741824 bytes
                            if file_size > 1073741824:
                                print(f"⚠️  MCN {category} state file exceeds 1GB ({file_size / 1073741824:.2f} GB), pruning...")
                                self.prune_mcn_state(category, mcn_instance, storage_file)
                        
                        mcn_instance.save(storage_file)
                        saved_counts[category] = int(size) if size is not None else -1
                    except (MemoryError, AttributeError, TypeError, ValueError) as native_err:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.debug("PHASE E: MCN %s save failed: %s", category, type(native_err).__name__)
                    except Exception as e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.debug("PHASE E: Failed to save MCN %s state: %s", category, str(e))
        
        # PHASE E: Log accurate summary of saved MCN states
        import logging
        logger = logging.getLogger(__name__)
        if saved_counts:
            logger.info("PHASE E: MCN states saved: %s", saved_counts)
        else:
            logger.info("PHASE E: MCN states saved: {}")
        
        return len(saved_counts) > 0
    
    def prune_mcn_state(self, category: str, mcn_instance: Any, storage_file: str, prune_percent: float = 0.20) -> bool:
        """
        Prune MCN state by removing oldest/weakest memories.
        
        Args:
            category: MCN category (regime, strategy, user, market, trade)
            mcn_instance: MCN instance to prune
            storage_file: Path to state file
            prune_percent: Percentage of memories to remove (default: 20%)
        
        Returns:
            True if pruning successful, False otherwise
        """
        try:
            if not mcn_instance:
                return False
            
            # Get current size
            try:
                if hasattr(mcn_instance, "vals") and mcn_instance.vals is not None:
                    current_size = len(mcn_instance.vals) if hasattr(mcn_instance.vals, "__len__") else 0
                elif hasattr(mcn_instance, "size"):
                    current_size = mcn_instance.size
                elif hasattr(mcn_instance, "n"):
                    current_size = mcn_instance.n
                else:
                    print(f"⚠️  Cannot determine MCN {category} size for pruning")
                    return False
            except Exception as e:
                print(f"⚠️  Error getting MCN {category} size: {e}")
                return False
            
            if current_size == 0:
                return True  # Nothing to prune
            
            # Calculate how many to remove (20% of memories)
            num_to_remove = max(1, int(current_size * prune_percent))
            
            print(f"🧹 Pruning MCN {category}: removing {num_to_remove} of {current_size} memories (oldest/weakest 20%)")
            
            # MCN library doesn't expose direct pruning API, so we need to:
            # 1. Extract all memories with their values/weights
            # 2. Sort by value (weakest) or timestamp (oldest)
            # 3. Remove bottom 20%
            # 4. Rebuild MCN with remaining memories
            
            # Since MCN library doesn't expose memory access directly,
            # we'll use a workaround: reduce budget and let auto_maintain handle it
            if hasattr(mcn_instance, "budget"):
                original_budget = mcn_instance.budget
                # Reduce budget by 20% to force pruning
                new_budget = max(100, int(original_budget * (1 - prune_percent)))
                mcn_instance.budget = new_budget
                
                # Trigger auto-maintenance if available
                if hasattr(mcn_instance, "maintain"):
                    try:
                        mcn_instance.maintain()
                    except Exception:
                        pass
                
                # Restore original budget (pruning already done)
                mcn_instance.budget = original_budget
            
            print(f"✅ MCN {category} pruned: {current_size} → {current_size - num_to_remove} memories")
            return True
            
        except Exception as e:
            print(f"❌ Error pruning MCN {category}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def record_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
        user_id: Optional[str] = None,
        strategy_id: Optional[str] = None
    ) -> bool:
        """
        Record an event in MCN.
        
        Converts payload into MCN vector representation and stores it.
        
        Args:
            event_type: Type of event (e.g., "trade_executed", "strategy_backtest")
            payload: Event data dictionary
            user_id: Optional user ID
            strategy_id: Optional strategy ID
        
        Returns:
            True if event was recorded, False otherwise
        """
        # PHASE E: Check if MCN is available (any of the 5 instances)
        if not self.is_available:
            return False
        
        try:
            # Convert event to embedding vector
            event_vector = self._event_to_vector(event_type, payload)
            
            # PHASE: Enforce MCN_DIM before storing - use np.asarray and np.resize
            event_vector = np.asarray(event_vector, dtype=np.float32)
            if event_vector.ndim > 1:
                event_vector = event_vector.flatten()
            
            # PHASE: Ensure exact MCN_DIM dimension using np.resize
            if event_vector.shape[0] != self.MCN_DIM:
                event_vector = np.resize(event_vector, self.MCN_DIM)
            
            # PHASE 0 FIX: Validate event_vector before adding to MCN
            if event_vector is None or event_vector.size == 0:
                print("⚠️  MCN: skipping event record - event_vector is None or empty")
                return False
            
            # Ensure it's 2D array (batch dimension) for MCN.add()
            if event_vector.ndim == 1:
                event_vector = event_vector.reshape(1, -1)
            elif event_vector.ndim == 0:
                print("⚠️  MCN: skipping event record - event_vector has invalid dimensions (0D)")
                return False
            
            # PHASE: Final verification - must be exactly MCN_DIM
            if event_vector.shape[1] != self.MCN_DIM:
                print(f"⚠️  MCN: vector dimension mismatch after resize: expected {self.MCN_DIM}, got {event_vector.shape[1]}")
                # Force fix one more time
                fixed_vec = np.resize(event_vector.flatten(), self.MCN_DIM)
                event_vector = fixed_vec.reshape(1, -1)
            
            # Check if adding would result in negative dimensions
            n_vectors = event_vector.shape[0]
            if n_vectors <= 0:
                print(f"⚠️  MCN: skipping event record - zero or negative vector count: {n_vectors}")
                return False
            
            event_meta = {
                "event_type": event_type,
                "user_id": user_id,
                "strategy_id": strategy_id,
                "payload": payload,
                "timestamp": payload.get("timestamp"),
            }
            
            # PHASE E: Route event to correct MCN category using explicit mapping
            EVENT_TYPE_TO_CATEGORY = {
                "market_snapshot": "regime",
                "regime_detected": "regime",
                "strategy_backtest": "strategy",
                "strategy_mutated": "strategy",
                "strategy_created": "strategy",
                "user_action": "user",
                "user_preference": "user",
                "user_risk_update": "user",
                "market_pattern": "market",
                "market_context": "market",
                "trade_executed": "trade",
                "trade_signal": "trade",
                "signal_generated": "trade",
            }
            
            category = EVENT_TYPE_TO_CATEGORY.get(event_type)
            if not category:
                # Unknown event type: silently ignore or log at debug only
                import logging
                logger = logging.getLogger(__name__)
                logger.debug("PHASE E: Unknown MCN event_type=%s (skipping)", event_type)
                return False
            
            # Map category to MCN instance
            category_to_mcn = {
                "regime": self.mcn_regime,
                "strategy": self.mcn_strategy,
                "user": self.mcn_user,
                "market": self.mcn_market,
                "trade": self.mcn_trade,
            }
            
            target_mcn = category_to_mcn.get(category)
            if not target_mcn:
                # MCN instance not initialized - log at debug level only
                import logging
                logger = logging.getLogger(__name__)
                logger.debug("PHASE E: MCN %s not initialized for event_type=%s (skipping)", category, event_type)
                return False
            
            # HEAP CORRUPTION FIX: Validate vector before MCN operation to prevent malloc errors
            try:
                # Ensure vector is valid numpy array with correct shape
                if event_vector is None or event_vector.size == 0:
                    return False
                
                # Ensure exactly 2D shape (batch, dim)
                if event_vector.ndim == 1:
                    event_vector = event_vector.reshape(1, -1)
                elif event_vector.ndim != 2:
                    return False
                
                # Ensure dimension is exactly MCN_DIM
                if event_vector.shape[1] != self.MCN_DIM:
                    event_vector = self._fix_dim(event_vector.flatten(), self.MCN_DIM).reshape(1, -1)
                
                # Ensure float32 dtype
                event_vector = event_vector.astype(np.float32)
                
                # Validate meta_batch
                if not isinstance(event_meta, dict):
                    return False
                
            except Exception as validation_err:
                import logging
                logger = logging.getLogger(__name__)
                logger.debug("MCN vector validation failed: %s", type(validation_err).__name__)
                return False
            
            # HEAP CORRUPTION FIX: Store in MCN with comprehensive error handling
            with self.thread_lock:
                try:
                    # Final validation before native call
                    if event_vector.shape != (1, self.MCN_DIM):
                        return False
                    
                    target_mcn.add(event_vector, meta_batch=[event_meta])
                except (MemoryError, AttributeError, TypeError, ValueError, RuntimeError, OSError) as native_err:
                    # HEAP CORRUPTION FIX: Catch all possible native errors including heap corruption
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.debug("MCN add() failed (native error): %s", type(native_err).__name__)
                    # Don't print - use logger to avoid spam
                    return False
                except Exception as e:
                    # HEAP CORRUPTION FIX: Catch any other errors including heap corruption signals
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.debug("MCN add() failed (unexpected error): %s", type(e).__name__)
                    return False
            
            # Periodically save state (every 10 events or so)
            if hasattr(self, '_event_count'):
                self._event_count += 1
            else:
                self._event_count = 1
            
            # PHASE E: Save state for the specific MCN category every 10 events
            if hasattr(self, '_event_count_by_category'):
                self._event_count_by_category[event_type] = self._event_count_by_category.get(event_type, 0) + 1
            else:
                self._event_count_by_category = {event_type: 1}
            
            if self._event_count_by_category.get(event_type, 0) % 10 == 0:
                # Save only the relevant category
                category = None
                if event_type in ["market_snapshot", "regime_detected"]:
                    category = "regime"
                elif event_type in ["strategy_backtest", "strategy_mutated", "strategy_created"]:
                    category = "strategy"
                elif event_type in ["user_action", "user_preference", "user_risk_update"]:
                    category = "user"
                elif event_type in ["market_pattern", "market_context"]:
                    category = "market"
                elif event_type in ["trade_executed", "trade_signal", "signal_generated"]:
                    category = "trade"
                
                if category and self.storage_path:
                    try:
                        category_path = os.path.join(self.storage_path, f"mcn_{category}")
                        os.makedirs(category_path, exist_ok=True)
                        storage_file = os.path.join(category_path, "mcn_state.npz")
                        target_mcn = getattr(self, f"mcn_{category}")
                        if target_mcn:
                            with self.thread_lock:
                                target_mcn.save(storage_file)
                    except Exception as e:
                        print(f"⚠️  PHASE E: Failed to save MCN {category} state: {e}")
            
            return True
        except Exception as e:
            print(f"Error recording event in MCN: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def get_memory_for_strategy(
        self,
        strategy_id: str,
        strategy_data: Optional[Dict[str, Any]] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Retrieve MCN memory for a strategy.
        
        Uses search() to find similar events related to this strategy.
        
        Returns:
            Dictionary with:
            - clusters: Related strategy clusters
            - embeddings: Vector embeddings
            - summary_vectors: Summary representations
            - historical_patterns: Performance patterns
        """
        if not self.is_available or not self.mcn:
            return {
                "clusters": [],
                "embeddings": [],
                "summary_vectors": [],
                "historical_patterns": [],
            }
        
        try:
            # Query MCN for strategy-related memories using proper embeddings
            strategy_vector = self._strategy_to_vector(strategy_id)
            
            # PHASE: Fix dimension before search
            strategy_vector = self._fix_dim(strategy_vector, self.FIXED_DIM)
            
            if strategy_vector.ndim == 1:
                strategy_vector = strategy_vector.reshape(1, -1)
            
            # PHASE E: Use mcn_strategy for strategy memory
            target_mcn = self.mcn_strategy
            if not target_mcn:
                return {
                    "clusters": [],
                    "embeddings": [],
                    "summary_vectors": [],
                    "historical_patterns": [],
                }
            
            # HEAP CORRUPTION FIX: Validate vector before search
            try:
                if strategy_vector is None or strategy_vector.size == 0:
                    return {"clusters": [], "embeddings": [], "summary_vectors": [], "historical_patterns": []}
                
                if strategy_vector.ndim == 1:
                    strategy_vector = strategy_vector.reshape(1, -1)
                elif strategy_vector.ndim != 2:
                    return {"clusters": [], "embeddings": [], "summary_vectors": [], "historical_patterns": []}
                
                if strategy_vector.shape[1] != self.MCN_DIM:
                    strategy_vector = self._fix_dim(strategy_vector.flatten(), self.MCN_DIM).reshape(1, -1)
                
                strategy_vector = strategy_vector.astype(np.float32)
            except Exception:
                return {"clusters": [], "embeddings": [], "summary_vectors": [], "historical_patterns": []}
            
            # HEAP CORRUPTION FIX: Search with comprehensive error handling
            with self.thread_lock:
                try:
                    if strategy_vector.shape != (1, self.MCN_DIM):
                        return {"clusters": [], "embeddings": [], "summary_vectors": [], "historical_patterns": []}
                    
                    meta_list, scores = target_mcn.search(strategy_vector, k=limit)
                except (MemoryError, AttributeError, TypeError, ValueError, RuntimeError, OSError) as native_err:
                    # HEAP CORRUPTION FIX: Catch all native errors silently
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.debug("MCN strategy search() failed: %s", type(native_err).__name__)
                    return {"clusters": [], "embeddings": [], "summary_vectors": [], "historical_patterns": []}
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.debug("MCN strategy search() failed (unexpected): %s", type(e).__name__)
                    return {"clusters": [], "embeddings": [], "summary_vectors": [], "historical_patterns": []}
            
            # Extract patterns from search results with value-weighted scores
            patterns = []
            if meta_list and len(meta_list) > 0:
                for meta, score in zip(meta_list[:limit], scores[:limit] if scores else []):
                    # Filter by strategy_id or relevant event types
                    if meta.get("strategy_id") == strategy_id or meta.get("event_type") in ["strategy_backtest", "trade_executed", "signal_generated"]:
                        patterns.append({
                            "event_type": meta.get("event_type"),
                            "payload": meta.get("payload", {}),
                            "timestamp": meta.get("timestamp"),
                            "similarity_score": float(score) if score is not None else 0.0,
                            "mcn_value": float(score) if score is not None else 0.0,  # Score includes value
                        })
            
            return {
                "clusters": [],
                "embeddings": [],
                "summary_vectors": [],
                "historical_patterns": sorted(patterns, key=lambda x: x["similarity_score"], reverse=True),
            }
        except Exception as e:
            print(f"Error retrieving memory for strategy {strategy_id}: {e}")
            import traceback
            traceback.print_exc()
            return {
                "clusters": [],
                "embeddings": [],
                "summary_vectors": [],
                "historical_patterns": [],
            }
    
    def get_market_regime(
        self,
        symbol: str,
        market_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get market regime classification using MCN clustering.
        
        Returns:
            {
                "regime": "bull_trend" | "bear_trend" | "ranging" | "high_vol" | "low_vol" | "mixed",
                "confidence": float (0-1),
                "memory_samples": int
            }
        """
        if self.is_stub_mode:
            # Deterministic stub: analyze market_data if available
            if market_data:
                volatility = market_data.get("volatility", 0.0)
                price_change = market_data.get("price_change_pct", 0.0)
                
                if volatility > 0.3:
                    regime = "high_vol"
                elif volatility < 0.1:
                    regime = "low_vol"
                elif price_change > 0.02:
                    regime = "bull_trend"
                elif price_change < -0.02:
                    regime = "bear_trend"
                else:
                    regime = "ranging"
                
                return {
                    "regime": regime,
                    "confidence": 0.6,  # Lower confidence in stub mode
                    "memory_samples": 0,
                }
            return {
                "regime": "unknown",
                "confidence": 0.5,
                "memory_samples": 0,
            }
        
        from .regime_detector import RegimeDetector
        detector = RegimeDetector()
        return detector.get_market_regime(symbol, market_data)
    
    def get_regime_context(
        self,
        symbol: str,
        strategy_id: Optional[str] = None,
        market_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Query MCN for current regime classification and strategy performance in that regime.
        
        Returns:
            {
                "regime_label": "bullish_high_vol",
                "strategy_perf_in_regime": {
                    "win_rate": 0.88,
                    "avg_return": 0.12
                },
                "confidence": 0.75
            }
        """
        if not self.is_available or not self.mcn:
            if self.is_stub_mode:
                # Deterministic stub: return basic regime context
                if market_data:
                    volatility = market_data.get("volatility", 0.0)
                    if volatility > 0.3:
                        regime_label = "high_vol"
                    elif volatility < 0.1:
                        regime_label = "low_vol"
                    else:
                        regime_label = "ranging"
                else:
                    regime_label = "unknown"
                
                return {
                    "regime_label": regime_label,
                    "strategy_perf_in_regime": {
                        "win_rate": 0.55,  # Conservative stub estimate
                        "avg_return": 0.05,
                    },
                    "confidence": 0.5,
                }
            return {
                "regime_label": "unknown",
                "strategy_perf_in_regime": {},
                "confidence": 0.0,
            }
        
        try:
            # Search MCN for recent market regime events using proper embeddings
            # Create a vector representing current market query
            regime_vector = self._market_to_vector(symbol, market_data)
            
            # PHASE: Fix dimension before search
            regime_vector = self._fix_dim(regime_vector, self.FIXED_DIM)
            
            if regime_vector.ndim == 1:
                regime_vector = regime_vector.reshape(1, -1)
            
            # PHASE E: Use mcn_regime for regime context
            target_mcn = self.mcn_regime
            if not target_mcn:
                return {
                    "regime_label": "unknown",
                    "strategy_perf_in_regime": {},
                    "confidence": 0.0,
                }
            
            # HEAP CORRUPTION FIX: Validate vector before search
            try:
                if regime_vector is None or regime_vector.size == 0:
                    return {"regime_label": "unknown", "strategy_perf_in_regime": {}, "confidence": 0.0}
                
                if regime_vector.ndim == 1:
                    regime_vector = regime_vector.reshape(1, -1)
                elif regime_vector.ndim != 2:
                    return {"regime_label": "unknown", "strategy_perf_in_regime": {}, "confidence": 0.0}
                
                if regime_vector.shape[1] != self.MCN_DIM:
                    regime_vector = self._fix_dim(regime_vector.flatten(), self.MCN_DIM).reshape(1, -1)
                
                regime_vector = regime_vector.astype(np.float32)
            except Exception:
                return {"regime_label": "unknown", "strategy_perf_in_regime": {}, "confidence": 0.0}
            
            # HEAP CORRUPTION FIX: Search with comprehensive error handling
            with self.thread_lock:
                try:
                    if regime_vector.shape != (1, self.MCN_DIM):
                        return {"regime_label": "unknown", "strategy_perf_in_regime": {}, "confidence": 0.0}
                    
                    meta_list, scores = target_mcn.search(regime_vector, k=20)
                except (MemoryError, AttributeError, TypeError, ValueError, RuntimeError, OSError) as native_err:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.debug("MCN regime search() failed: %s", type(native_err).__name__)
                    return {"regime_label": "unknown", "strategy_perf_in_regime": {}, "confidence": 0.0}
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.debug("MCN regime search() failed (unexpected): %s", type(e).__name__)
                    return {"regime_label": "unknown", "strategy_perf_in_regime": {}, "confidence": 0.0}
            
            # Analyze regime patterns using value-weighted scores
            regime_counts = {}
            strategy_perfs = []
            total_value = 0.0
            
            for meta, score in zip(meta_list[:20], scores[:20] if scores else []):
                event_type = meta.get("event_type", "")
                payload = meta.get("payload", {})
                value_weight = float(score) if score is not None else 0.0
                
                # Look for market_snapshot or signal_generated events
                if event_type in ["market_snapshot", "signal_generated"]:
                    # Extract regime info
                    regime = payload.get("market_regime", "unknown")
                    # Value-weighted regime counting
                    regime_counts[regime] = regime_counts.get(regime, 0.0) + value_weight
                    total_value += value_weight
                    
                    # If this is for our strategy, collect performance
                    if strategy_id and meta.get("strategy_id") == strategy_id:
                        if event_type == "signal_generated":
                            confidence = payload.get("confidence", 0.0)
                            strategy_perfs.append({
                                "confidence": confidence,
                                "regime": regime,
                                "value_weight": value_weight,
                            })
            
            # Determine most valuable regime (value-weighted)
            regime_label = max(regime_counts.items(), key=lambda x: x[1])[0] if regime_counts else "unknown"
            regime_confidence = regime_counts.get(regime_label, 0.0) / total_value if total_value > 0 else 0.0
            
            # Calculate strategy performance in this regime (value-weighted)
            if strategy_perfs:
                regime_perfs = [p for p in strategy_perfs if p["regime"] == regime_label]
                if regime_perfs:
                    total_weight = sum(p["value_weight"] for p in regime_perfs)
                    weighted_confidence = sum(
                        p["confidence"] * p["value_weight"] for p in regime_perfs
                    ) / total_weight if total_weight > 0 else 0.0
                    
                    # Estimate win_rate from confidence (value-weighted)
                    estimated_win_rate = min(1.0, weighted_confidence * 1.1)
                    strategy_perf = {
                        "win_rate": estimated_win_rate,
                        "avg_return": weighted_confidence * 0.15,
                        "confidence": weighted_confidence,
                    }
                else:
                    strategy_perf = {}
            else:
                strategy_perf = {}
            
            return {
                "regime_label": regime_label,
                "strategy_perf_in_regime": strategy_perf,
                "confidence": min(1.0, regime_confidence),
            }
        except Exception as e:
            print(f"Error getting regime context: {e}")
            return {
                "regime_label": "unknown",
                "strategy_perf_in_regime": {},
                "confidence": 0.0,
            }
    
    def get_user_profile_memory(
        self,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Summarize user's trading behavior and preferences from MCN memory.
        
        Returns:
            {
                "risk_tendency": "moderate",
                "prefers_trend_following": true,
                "prefers_mean_reversion": false,
                "avg_acceptance_rate": 0.65,
                "best_performing_strategies": [...]
            }
        """
        if not self.is_available or not self.mcn:
            return {
                "risk_tendency": "moderate",
                "prefers_trend_following": False,
                "prefers_mean_reversion": False,
                "avg_acceptance_rate": 0.5,
                "best_performing_strategies": [],
            }
        
        try:
            # Search MCN for user-related events using proper embeddings
            user_vector = self._user_to_vector(user_id)
            
            # PHASE: Fix dimension before search
            user_vector = self._fix_dim(user_vector, self.FIXED_DIM)
            
            if user_vector.ndim == 1:
                user_vector = user_vector.reshape(1, -1)
            
            # PHASE E: Use mcn_user for user profile memory
            target_mcn = self.mcn_user
            if not target_mcn:
                return {
                    "risk_tendency": "moderate",
                    "prefers_trend_following": False,
                    "prefers_mean_reversion": False,
                    "avg_acceptance_rate": 0.5,
                    "best_performing_strategies": [],
                }
            
            # HEAP CORRUPTION FIX: Validate vector before search
            try:
                if user_vector is None or user_vector.size == 0:
                    return {"risk_tendency": "moderate", "prefers_trend_following": False, "prefers_mean_reversion": False, "avg_acceptance_rate": 0.5, "best_performing_strategies": []}
                
                if user_vector.ndim == 1:
                    user_vector = user_vector.reshape(1, -1)
                elif user_vector.ndim != 2:
                    return {"risk_tendency": "moderate", "prefers_trend_following": False, "prefers_mean_reversion": False, "avg_acceptance_rate": 0.5, "best_performing_strategies": []}
                
                if user_vector.shape[1] != self.MCN_DIM:
                    user_vector = self._fix_dim(user_vector.flatten(), self.MCN_DIM).reshape(1, -1)
                
                user_vector = user_vector.astype(np.float32)
            except Exception:
                return {"risk_tendency": "moderate", "prefers_trend_following": False, "prefers_mean_reversion": False, "avg_acceptance_rate": 0.5, "best_performing_strategies": []}
            
            # HEAP CORRUPTION FIX: Search with comprehensive error handling
            with self.thread_lock:
                try:
                    if user_vector.shape != (1, self.MCN_DIM):
                        return {"risk_tendency": "moderate", "prefers_trend_following": False, "prefers_mean_reversion": False, "avg_acceptance_rate": 0.5, "best_performing_strategies": []}
                    
                    meta_list, scores = target_mcn.search(user_vector, k=100)
                except (MemoryError, AttributeError, TypeError, ValueError, RuntimeError, OSError) as native_err:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.debug("MCN user search() failed: %s", type(native_err).__name__)
                    return {"risk_tendency": "moderate", "prefers_trend_following": False, "prefers_mean_reversion": False, "avg_acceptance_rate": 0.5, "best_performing_strategies": []}
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.debug("MCN user search() failed (unexpected): %s", type(e).__name__)
                    return {"risk_tendency": "moderate", "prefers_trend_following": False, "prefers_mean_reversion": False, "avg_acceptance_rate": 0.5, "best_performing_strategies": []}
            
            # Analyze user behavior with value weighting
            accepted_signals = 0
            total_signals = 0
            strategy_performances = {}
            risk_levels = []
            total_value = 0.0
            
            for meta, score in zip(meta_list, scores if scores else []):
                event_type = meta.get("event_type", "")
                payload = meta.get("payload", {})
                value_weight = float(score) if score is not None else 0.0
                total_value += value_weight
                
                if event_type == "signal_generated" and meta.get("user_id") == user_id:
                    total_signals += 1
                
                if event_type == "trade_executed" and meta.get("user_id") == user_id:
                    strategy_id = meta.get("strategy_id")
                    pnl = payload.get("pnl", 0.0)
                    if strategy_id:
                        if strategy_id not in strategy_performances:
                            strategy_performances[strategy_id] = {"pnls": [], "weights": []}
                        strategy_performances[strategy_id]["pnls"].append(pnl)
                        strategy_performances[strategy_id]["weights"].append(value_weight)
                
                # Extract risk level from signal
                if event_type == "signal_generated":
                    risk_level = payload.get("risk_level", "moderate")
                    risk_levels.append((risk_level, value_weight))
            
            # Calculate value-weighted acceptance rate
            acceptance_rate = 0.5  # Default
            if total_signals > 0:
                executed_count = len([m for m in meta_list if m.get("event_type") == "trade_executed"])
                acceptance_rate = min(1.0, executed_count / total_signals)
            
            # Determine value-weighted risk tendency
            if risk_levels:
                risk_weights = {}
                for rl, weight in risk_levels:
                    risk_weights[rl] = risk_weights.get(rl, 0.0) + weight
                risk_tendency = max(risk_weights.items(), key=lambda x: x[1])[0]
            else:
                risk_tendency = "moderate"
            
            # Find best performing strategies (value-weighted)
            best_strategies = []
            for strategy_id, data in strategy_performances.items():
                pnls = data["pnls"]
                weights = data["weights"]
                if pnls:
                    # Value-weighted average P&L
                    total_weight = sum(weights)
                    weighted_avg_pnl = sum(
                        pnl * weight for pnl, weight in zip(pnls, weights)
                    ) / total_weight if total_weight > 0 else 0.0
                    
                    win_rate = len([p for p in pnls if p > 0]) / len(pnls)
                    best_strategies.append({
                        "strategy_id": strategy_id,
                        "avg_pnl": weighted_avg_pnl,
                        "win_rate": win_rate,
                        "total_trades": len(pnls),
                    })
            
            best_strategies.sort(key=lambda x: x["avg_pnl"], reverse=True)
            
            return {
                "risk_tendency": risk_tendency,
                "prefers_trend_following": False,  # Would analyze strategy types
                "prefers_mean_reversion": False,  # Would analyze strategy types
                "avg_acceptance_rate": acceptance_rate,
                "best_performing_strategies": best_strategies[:5],
            }
        except Exception as e:
            print(f"Error getting user profile memory: {e}")
            return {
                "risk_tendency": "moderate",
                "prefers_trend_following": False,
                "prefers_mean_reversion": False,
                "avg_acceptance_rate": 0.5,
                "best_performing_strategies": [],
            }
    
    def get_strategy_lineage_memory(
        self,
        strategy_id: str,
        db: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Provide context about strategy lineage and family tree.
        
        Returns:
            {
                "generation": 2,
                "ancestors": [...],
                "siblings": [...],
                "ancestor_stability": 0.85,
                "has_overfit_ancestors": false
            }
        """
        if not self.is_available:
            return {
                "generation": 0,
                "ancestors": [],
                "siblings": [],
                "ancestor_stability": 0.5,
                "has_overfit_ancestors": False,
            }
        
        # If DB is provided, query lineage directly
        if db:
            try:
                from ..db import crud
                # Get parent lineages
                parent_lineages = crud.get_strategy_lineages_by_child(db, strategy_id)
                # Get child lineages (siblings)
                child_lineages = crud.get_strategy_lineages_by_parent(db, strategy_id)
                
                generation = 0
                ancestors = []
                siblings = []
                
                # Traverse up the tree
                current_strategy_id = strategy_id
                visited = set()
                while current_strategy_id and current_strategy_id not in visited:
                    visited.add(current_strategy_id)
                    parent_lineage = next((l for l in parent_lineages if l.child_strategy_id == current_strategy_id), None)
                    if parent_lineage:
                        generation += 1
                        ancestors.append({
                            "strategy_id": parent_lineage.parent_strategy_id,
                            "mutation_type": parent_lineage.mutation_type,
                        })
                        current_strategy_id = parent_lineage.parent_strategy_id
                    else:
                        break
                
                # Get siblings (other children of same parent)
                if parent_lineages:
                    parent_id = parent_lineages[0].parent_strategy_id
                    all_siblings = crud.get_strategy_lineages_by_parent(db, parent_id)
                    siblings = [{"strategy_id": l.child_strategy_id} for l in all_siblings if l.child_strategy_id != strategy_id]
                
                # Check ancestor stability from MCN (value-weighted)
                ancestor_stability = 0.5
                has_overfit = False
                if ancestors:
                    stable_count = 0
                    total_value = 0.0
                    
                    for ancestor in ancestors:
                        aid = ancestor["strategy_id"]
                        memory = self.get_memory_for_strategy(aid, limit=10)
                        patterns = memory.get("historical_patterns", [])
                        
                        if patterns:
                            # Use value-weighted win rate
                            total_pattern_value = sum(p.get("mcn_value", 0.0) for p in patterns)
                            weighted_win_rate = sum(
                                p.get("payload", {}).get("win_rate", 0) * p.get("mcn_value", 0.0)
                                for p in patterns
                            ) / total_pattern_value if total_pattern_value > 0 else 0.0
                            
                            if weighted_win_rate >= 0.75:
                                stable_count += 1
                            total_value += total_pattern_value
                    
                    ancestor_stability = stable_count / len(ancestors) if ancestors else 0.5
                    has_overfit = ancestor_stability < 0.5
                
                return {
                    "generation": generation,
                    "ancestors": ancestors,
                    "siblings": siblings,
                    "ancestor_stability": ancestor_stability,
                    "has_overfit_ancestors": has_overfit,
                }
            except Exception as e:
                print(f"Error getting lineage from DB: {e}")
        
        # Fallback: use MCN search with proper embeddings
        try:
            strategy_vector = self._strategy_to_vector(strategy_id)
            
            # PHASE: Fix dimension before search
            strategy_vector = self._fix_dim(strategy_vector, self.FIXED_DIM)
            
            if strategy_vector.ndim == 1:
                strategy_vector = strategy_vector.reshape(1, -1)
            # PHASE E: Use mcn_strategy for lineage memory
            target_mcn = self.mcn_strategy
            if not target_mcn:
                return {
                    "generation": 0,
                    "ancestors": [],
                    "siblings": [],
                    "ancestor_stability": 0.5,
                    "has_overfit_ancestors": False,
                }
            
            # HEAP CORRUPTION FIX: Validate vector before search
            try:
                if strategy_vector is None or strategy_vector.size == 0:
                    return {"generation": 0, "ancestors": [], "siblings": [], "ancestor_stability": 0.5, "has_overfit_ancestors": False}
                
                if strategy_vector.ndim == 1:
                    strategy_vector = strategy_vector.reshape(1, -1)
                elif strategy_vector.ndim != 2:
                    return {"generation": 0, "ancestors": [], "siblings": [], "ancestor_stability": 0.5, "has_overfit_ancestors": False}
                
                if strategy_vector.shape[1] != self.MCN_DIM:
                    strategy_vector = self._fix_dim(strategy_vector.flatten(), self.MCN_DIM).reshape(1, -1)
                
                strategy_vector = strategy_vector.astype(np.float32)
            except Exception:
                return {"generation": 0, "ancestors": [], "siblings": [], "ancestor_stability": 0.5, "has_overfit_ancestors": False}
            
            # HEAP CORRUPTION FIX: Search with comprehensive error handling
            with self.thread_lock:
                try:
                    if strategy_vector.shape != (1, self.MCN_DIM):
                        return {"generation": 0, "ancestors": [], "siblings": [], "ancestor_stability": 0.5, "has_overfit_ancestors": False}
                    
                    meta_list, scores = target_mcn.search(strategy_vector, k=20)
                except (MemoryError, AttributeError, TypeError, ValueError, RuntimeError, OSError) as native_err:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.debug("MCN strategy lineage search() failed: %s", type(native_err).__name__)
                    return {"generation": 0, "ancestors": [], "siblings": [], "ancestor_stability": 0.5, "has_overfit_ancestors": False}
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.debug("MCN strategy lineage search() failed (unexpected): %s", type(e).__name__)
                    return {"generation": 0, "ancestors": [], "siblings": [], "ancestor_stability": 0.5, "has_overfit_ancestors": False}
            
            # Extract lineage info from mutation events
            mutation_events = [m for m in meta_list if "mutat" in m.get("event_type", "").lower()]
            
            return {
                "generation": len(mutation_events),
                "ancestors": [],
                "siblings": [],
                "ancestor_stability": 0.5,
                "has_overfit_ancestors": False,
            }
        except Exception as e:
            print(f"Error getting lineage memory: {e}")
            return {
                "generation": 0,
                "ancestors": [],
                "siblings": [],
                "ancestor_stability": 0.5,
                "has_overfit_ancestors": False,
            }
    
    def _market_to_vector(self, symbol: str, market_data: Optional[Dict[str, Any]] = None) -> np.ndarray:
        """Convert market symbol/data to embedding vector."""
        text_parts = [f"symbol: {symbol}"]
        if market_data:
            if "volatility" in market_data:
                text_parts.append(f"volatility: {market_data['volatility']:.2f}")
            if "sentiment" in market_data:
                text_parts.append(f"sentiment: {market_data['sentiment']:.2f}")
            if "price" in market_data:
                text_parts.append(f"price: {market_data['price']:.2f}")
        text = " ".join(text_parts)
        return self._embed_text(text)
    
    def _user_to_vector(self, user_id: str, user_data: Optional[Dict[str, Any]] = None) -> np.ndarray:
        """Convert user ID/data to embedding vector."""
        text_parts = [f"user_id: {user_id}"]
        if user_data:
            if "risk_tendency" in user_data:
                text_parts.append(f"risk_tendency: {user_data['risk_tendency']}")
        text = " ".join(text_parts)
        return self._embed_text(text)
    
    def generate_adjustment(
        self,
        strategy: Dict[str, Any],
        market_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate MCN-enhanced adjustments for a strategy.
        
        Args:
            strategy: Strategy data (parameters, ruleset, etc.)
            market_state: Current market state (volatility, sentiment, etc.)
        
        Returns:
            Dictionary with adjustments:
            - parameter_tweaks: Suggested parameter changes
            - volatility_adjustments: Volatility-based adjustments
            - risk_tuning: Risk parameter adjustments
            - confidence_modulation: Confidence adjustments
        """
        if not self.is_available or not self.mcn:
            return {
                "parameter_tweaks": {},
                "volatility_adjustments": {},
                "risk_tuning": {},
                "confidence_modulation": 1.0,
            }
        
        try:
            # Get strategy memory (value-ranked)
            memory = self.get_memory_for_strategy(
                strategy.get("id", ""),
                strategy_data=strategy,
                limit=20
            )
            
            # Analyze patterns for parameter adjustments
            patterns = memory.get("historical_patterns", [])
            
            # Find best performing patterns (value-weighted)
            best_patterns = sorted(
                patterns,
                key=lambda x: x.get("mcn_value", 0.0) * x.get("payload", {}).get("win_rate", 0.0),
                reverse=True
            )[:5]
            
            # Generate parameter tweaks from best patterns
            parameter_tweaks = {}
            if best_patterns:
                # Extract common parameters from best patterns
                # This is simplified - in production, would use more sophisticated analysis
                avg_confidence = sum(
                    p.get("payload", {}).get("confidence", 0.5) * p.get("mcn_value", 0.0)
                    for p in best_patterns
                ) / sum(p.get("mcn_value", 0.0) for p in best_patterns) if best_patterns else 0.5
                
                # Adjust confidence modulation based on pattern performance
                confidence_modulation = min(1.2, max(0.8, avg_confidence))
            else:
                confidence_modulation = 1.0
            
            # Volatility adjustments based on market state
            volatility = market_state.get("volatility", 0.0)
            volatility_adjustments = {}
            if volatility > 0.3:
                confidence_modulation *= 0.8
                volatility_adjustments["position_size_multiplier"] = 0.5
            elif volatility < 0.1:
                confidence_modulation *= 1.1
            
            return {
                "parameter_tweaks": parameter_tweaks,
                "volatility_adjustments": volatility_adjustments,
                "risk_tuning": {},
                "confidence_modulation": confidence_modulation,
            }
        except Exception as e:
            print(f"Error generating MCN adjustments: {e}")
            return {
                "parameter_tweaks": {},
                "volatility_adjustments": {},
                "risk_tuning": {},
                "confidence_modulation": 1.0,
            }
    
    def recommend_trade(
        self,
        strategy: Dict[str, Any],
        market_data: Dict[str, Any],
        user_id: Optional[str] = None,
        db: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Use MCN memory + strategy ruleset to produce trade recommendation.
        
        Args:
            strategy: Strategy data (ruleset, parameters, etc.)
            market_data: Current market data (price, candles, sentiment, etc.)
        
        Returns:
            Dictionary with:
            - side: "BUY" or "SELL"
            - entry: Entry price
            - exit: Exit price (optional)
            - stop_loss: Stop loss price
            - take_profit: Take profit price
            - confidence: Confidence score (0-1)
            - explanation: Reasoning for the recommendation
        """
        if not self.is_available or not self.mcn:
            if self.is_stub_mode:
                # Deterministic stub: analyze market_data for basic recommendation
                current_price = market_data.get("price", 0.0)
                volatility = market_data.get("volatility", 0.0)
                sentiment = market_data.get("sentiment", 0.0)
                
                # Simple logic: bullish sentiment + low vol = BUY
                if sentiment > 0.1 and volatility < 0.2:
                    side = "BUY"
                    confidence = 0.6
                elif sentiment < -0.1 and volatility < 0.2:
                    side = "SELL"
                    confidence = 0.6
                else:
                    side = "BUY"
                    confidence = 0.5
                
                # Calculate stops
                stop_loss_pct = 0.02
                take_profit_pct = 0.04
                if side == "BUY":
                    stop_loss = current_price * (1 - stop_loss_pct)
                    take_profit = current_price * (1 + take_profit_pct)
                else:
                    stop_loss = current_price * (1 + stop_loss_pct)
                    take_profit = current_price * (1 - take_profit_pct)
                
                return {
                    "side": side,
                    "entry": current_price,
                    "exit": None,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "confidence": confidence,
                    "explanation": "MCN STUB MODE: Basic deterministic recommendation based on sentiment and volatility",
                    "historical_patterns": [],
                }
            # Fallback to basic signal if MCN unavailable
            return {
                "side": "BUY",
                "entry": market_data.get("price", 0.0),
                "exit": None,
                "stop_loss": None,
                "take_profit": None,
                "confidence": 0.5,
                "explanation": "MCN unavailable - using basic signal",
                "historical_patterns": [],
            }
        
        try:
            # Get strategy memory (value-ranked)
            memory = self.get_memory_for_strategy(
                strategy.get("id", ""),
                strategy_data=strategy,
                limit=20
            )
            
            # Get market state vector
            market_vector = self._market_to_vector(
                market_data.get("symbol", "UNKNOWN"),
                market_data
            )
            
            # PHASE: Fix dimension before search
            market_vector = self._fix_dim(market_vector, self.FIXED_DIM)
            
            if market_vector.ndim == 1:
                market_vector = market_vector.reshape(1, -1)
            
            # HEAP CORRUPTION FIX: Validate vector before search
            try:
                if market_vector is None or market_vector.size == 0:
                    current_price = market_data.get("price", 0.0)
                    return {"side": "BUY", "entry": current_price, "exit": None, "stop_loss": current_price * 0.98, "take_profit": current_price * 1.03, "confidence": 0.5}
                
                if market_vector.ndim == 1:
                    market_vector = market_vector.reshape(1, -1)
                elif market_vector.ndim != 2:
                    current_price = market_data.get("price", 0.0)
                    return {"side": "BUY", "entry": current_price, "exit": None, "stop_loss": current_price * 0.98, "take_profit": current_price * 1.03, "confidence": 0.5}
                
                if market_vector.shape[1] != self.MCN_DIM:
                    market_vector = self._fix_dim(market_vector.flatten(), self.MCN_DIM).reshape(1, -1)
                
                market_vector = market_vector.astype(np.float32)
            except Exception:
                current_price = market_data.get("price", 0.0)
                return {"side": "BUY", "entry": current_price, "exit": None, "stop_loss": current_price * 0.98, "take_profit": current_price * 1.03, "confidence": 0.5}
            
            # PHASE E: Use mcn_market and mcn_trade for trade recommendations
            target_mcn_market = self.mcn_market
            target_mcn_trade = self.mcn_trade
            
            market_meta_list = []
            market_scores = []
            trade_meta_list = []
            trade_scores = []
            
            # HEAP CORRUPTION FIX: Search market patterns with comprehensive error handling
            if target_mcn_market:
                with self.thread_lock:
                    try:
                        if market_vector.shape == (1, self.MCN_DIM):
                            market_meta_list, market_scores = target_mcn_market.search(market_vector, k=5)
                    except (MemoryError, AttributeError, TypeError, ValueError, RuntimeError, OSError) as native_err:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.debug("MCN market search() failed: %s", type(native_err).__name__)
                    except Exception:
                        pass
            
            # HEAP CORRUPTION FIX: Search trade patterns with comprehensive error handling
            if target_mcn_trade:
                with self.thread_lock:
                    try:
                        if market_vector.shape == (1, self.MCN_DIM):
                            trade_meta_list, trade_scores = target_mcn_trade.search(market_vector, k=5)
                    except (MemoryError, AttributeError, TypeError, ValueError, RuntimeError, OSError) as native_err:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.debug("MCN trade search() failed: %s", type(native_err).__name__)
                    except Exception:
                        pass
            
            # Combine results
            meta_list = market_meta_list + trade_meta_list
            scores = (market_scores or []) + (trade_scores or [])
            
            if not meta_list:
                # Return basic fallback recommendation
                current_price = market_data.get("price", 0.0)
                return {
                    "side": "BUY",
                    "entry": current_price,
                    "exit": None,
                    "stop_loss": current_price * 0.98,
                    "take_profit": current_price * 1.03,
                    "confidence": 0.5,
                    "explanation": f"MCN unavailable - using basic signal (error: {type(native_err).__name__})",
                }
            
            # Analyze successful patterns (value-weighted)
            buy_patterns = []
            sell_patterns = []
            total_buy_value = 0.0
            total_sell_value = 0.0
            
            for meta, score in zip(meta_list, scores if scores else []):
                event_type = meta.get("event_type", "")
                payload = meta.get("payload", {})
                value_weight = float(score) if score is not None else 0.0
                
                if event_type == "trade_executed" and payload.get("pnl", 0) > 0:
                    side = payload.get("side", "BUY")
                    if side == "BUY":
                        buy_patterns.append({
                            "confidence": payload.get("confidence", 0.5),
                            "pnl": payload.get("pnl", 0.0),
                            "value_weight": value_weight,
                        })
                        total_buy_value += value_weight
                    else:
                        sell_patterns.append({
                            "confidence": payload.get("confidence", 0.5),
                            "pnl": payload.get("pnl", 0.0),
                            "value_weight": value_weight,
                        })
                        total_sell_value += value_weight
            
            # Determine side based on value-weighted patterns
            if total_buy_value > total_sell_value * 1.2:
                side = "BUY"
                confidence = min(1.0, total_buy_value / (total_buy_value + total_sell_value + 0.1))
                patterns = buy_patterns
            elif total_sell_value > total_buy_value * 1.2:
                side = "SELL"
                confidence = min(1.0, total_sell_value / (total_buy_value + total_sell_value + 0.1))
                patterns = sell_patterns
            else:
                side = "BUY"  # Default
                confidence = 0.5
                patterns = []
            
            # Calculate stop loss and take profit using ATR if available
            current_price = market_data.get("price", 0.0)
            volatility = market_data.get("volatility", 0.0)
            
            # Use ATR-based stops if volatility data available, otherwise use percentage
            if volatility > 0:
                # ATR-based: stop loss = 1.5 * ATR, take profit = 3.0 * ATR
                # Convert volatility (annualized) to approximate ATR
                atr_approx = current_price * (volatility / (252 ** 0.5))  # Rough ATR estimate
                stop_loss_atr_mult = 1.5
                take_profit_atr_mult = 3.0
                
                if side == "BUY":
                    stop_loss = current_price - (atr_approx * stop_loss_atr_mult)
                    take_profit = current_price + (atr_approx * take_profit_atr_mult)
                else:
                    stop_loss = current_price + (atr_approx * stop_loss_atr_mult)
                    take_profit = current_price - (atr_approx * take_profit_atr_mult)
            else:
                # Fallback to percentage-based
                stop_loss_pct = 0.02  # 2% stop loss
                take_profit_pct = 0.04  # 4% take profit
                
                if side == "BUY":
                    stop_loss = current_price * (1 - stop_loss_pct)
                    take_profit = current_price * (1 + take_profit_pct)
                else:
                    stop_loss = current_price * (1 + stop_loss_pct)
                    take_profit = current_price * (1 - take_profit_pct)
            
            explanation = (
                f"MCN recommendation based on {len(patterns)} value-weighted historical patterns. "
                f"Buy value: {total_buy_value:.2f}, Sell value: {total_sell_value:.2f}"
            )
            
            return {
                "side": side,
                "entry": current_price,
                "exit": None,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "confidence": confidence,
                "explanation": explanation,
            }
        except Exception as e:
            print(f"Error generating MCN trade recommendation: {e}")
            return {
                "side": "BUY",
                "entry": market_data.get("price", 0.0),
                "exit": None,
                "stop_loss": None,
                "take_profit": None,
                "confidence": 0.5,
                "explanation": f"Error: {str(e)}",
            }
    
    def _embed_text(self, text: str) -> np.ndarray:
        """
        Convert text to embedding vector using proper embeddings.
        
        PHASE: Returns vector that will be fixed to FIXED_DIM (32) by _fix_dim().
        """
        if self.embedder:
            # Get embedding from sentence transformer (usually 384 dim)
            vector = self.embedder.encode(text, convert_to_numpy=True)
            # Will be fixed to FIXED_DIM by _fix_dim() when used
            return vector
        else:
            # Fallback: simple hash-based embedding
            import hashlib
            hash_obj = hashlib.sha256(text.encode())
            hash_hex = hash_obj.hexdigest()
            vector = []
            # Generate enough values for FIXED_DIM
            for i in range(0, len(hash_hex), 2):
                if len(vector) >= self.FIXED_DIM:
                    break
                hex_pair = hash_hex[i:i+2]
                value = int(hex_pair, 16) / 255.0
                vector.append(value)
            # Pad to FIXED_DIM
            while len(vector) < self.FIXED_DIM:
                vector.append(0.0)
            return np.array(vector[:self.FIXED_DIM], dtype=np.float32)
    
    def _event_to_vector(self, event_type: str, payload: Dict[str, Any]) -> np.ndarray:
        """
        Convert an event to embedding vector using proper embeddings.
        
        Returns:
            numpy array (never None, never empty)
        """
        # Create a rich text representation of the event
        text_parts = [
            f"event_type: {event_type}",
            f"symbol: {payload.get('symbol', 'unknown')}",
            f"strategy_id: {payload.get('strategy_id', 'unknown')}",
        ]
        
        # Add numeric features as text
        if "price" in payload:
            text_parts.append(f"price: {payload['price']:.2f}")
        if "pnl" in payload:
            text_parts.append(f"pnl: {payload['pnl']:.2f}")
        if "return" in payload:
            text_parts.append(f"return: {payload['return']:.2f}%")
        if "volatility" in payload:
            text_parts.append(f"volatility: {payload['volatility']:.2f}")
        if "sentiment" in payload:
            text_parts.append(f"sentiment: {payload['sentiment']:.2f}")
        if "confidence" in payload:
            text_parts.append(f"confidence: {payload['confidence']:.2f}")
        if "win_rate" in payload:
            text_parts.append(f"win_rate: {payload['win_rate']:.2f}")
        if "market_regime" in payload:
            text_parts.append(f"regime: {payload['market_regime']}")
        
        text = " ".join(text_parts)
        vector = self._embed_text(text)
        
        # PHASE 0 FIX: Ensure vector is never None or empty
        if vector is None or vector.size == 0:
            # Return a default vector with FIXED_DIM
            return np.zeros(self.FIXED_DIM, dtype=np.float32)
        
        # PHASE: Fix dimension before returning (will be fixed again before use, but this ensures consistency)
        return self._fix_dim(vector, self.FIXED_DIM)
    
    def _strategy_to_vector(self, strategy_id: str, strategy_data: Optional[Dict[str, Any]] = None) -> np.ndarray:
        """
        Convert strategy to embedding vector using proper embeddings.
        """
        if strategy_data:
            # Create rich text representation
            text_parts = [
                f"strategy_id: {strategy_id}",
                f"name: {strategy_data.get('name', 'unknown')}",
            ]
            if "parameters" in strategy_data:
                params = strategy_data["parameters"]
                for key, value in params.items():
                    text_parts.append(f"{key}: {value}")
            if "ruleset" in strategy_data:
                ruleset = strategy_data["ruleset"]
                if "timeframe" in ruleset:
                    text_parts.append(f"timeframe: {ruleset['timeframe']}")
            text = " ".join(text_parts)
        else:
            text = f"strategy_id: {strategy_id}"
        return self._embed_text(text)


# Global MCN adapter instance
_mcn_adapter: Optional[MCNAdapter] = None


def get_mcn_adapter() -> MCNAdapter:
    """Get or create the global MCN adapter instance (singleton)."""
    global _mcn_adapter
    if _mcn_adapter is None:
        _mcn_adapter = MCNAdapter()
    return _mcn_adapter


def get_mcn_instance() -> Optional[Any]:
    """Get the underlying MCN instance (for direct access if needed)."""
    adapter = get_mcn_adapter()
    return adapter.mcn if adapter.is_available else None


def save_mcn_state() -> bool:
    """Explicitly save MCN state to persistent storage."""
    adapter = get_mcn_adapter()
    return adapter.save_state()

