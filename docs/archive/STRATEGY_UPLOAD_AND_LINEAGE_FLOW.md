# Strategy Upload, Storage, and Lineage Flow

## 1. Where Are User-Uploaded Strategies Saved?

**Answer: Strategies are saved in the PostgreSQL database, NOT as JSON files.**

### Storage Location:
- **Database Table:** `user_strategies`
- **Database:** PostgreSQL (via SQLAlchemy ORM)
- **Storage Format:** 
  - `ruleset` column: JSON (stores the strategy logic)
  - `parameters` column: JSON (stores strategy parameters)
  - `user_id` column: Foreign key linking to the original uploader

### Database Schema:
```sql
user_strategies (
    id: UUID (primary key)
    user_id: UUID (foreign key → users.id)  ← Original uploader
    name: String
    description: Text
    parameters: JSON  ← Strategy parameters
    ruleset: JSON     ← Strategy ruleset/logic
    asset_type: Enum
    status: String (pending_review, experiment, candidate, proposable, discarded)
    score: Float
    is_active: Boolean
    created_at: DateTime
    updated_at: DateTime
)
```

**Key Point:** The `user_id` field **always** points to the original uploader, even after mutations. This is how royalties are tracked.

---

## 2. Do Seeded and User-Uploaded Strategies Go Through Checks?

**Answer: YES, both go through checks, but with different flows:**

### User-Uploaded Strategy Flow:
```
User Uploads Strategy
    ↓
Status: pending_review
    ↓
Monitoring Worker (15 min cycle)
    ├─→ Duplicate Check (fingerprinting)
    ├─→ Sanity Check (lightweight backtest)
    └─→ Decision:
        ├─→ Duplicate → status: duplicate (rejected)
        ├─→ Failed → status: rejected
        └─→ Passed → status: experiment ✅
    ↓
Evolution Worker (8 min cycle)
    ├─→ Full Backtest
    ├─→ Calculate Metrics
    ├─→ Determine Status (experiment → candidate → proposable)
    ├─→ Mutate if needed
    └─→ Discard if failed
    ↓
Monitoring Worker (robustness check)
    ├─→ Calculate Robustness Score
    ├─→ Promote candidate → proposable (if meets criteria)
    └─→ Discard low performers
```

### Seed Strategy Flow:
```
System Startup
    ↓
Seed Loader
    ├─→ Load from seed_strategies/ (5 strategies)
    ├─→ Load from proven_strategies.json (40+ strategies)
    ├─→ Deduplicate using fingerprints
    └─→ Create with status: experiment (skips pending_review)
    ↓
Monitoring Worker (robustness check)
    ├─→ Calculate Robustness Score
    └─→ Promote if meets criteria
    ↓
Evolution Worker
    ├─→ Backtest
    ├─→ Mutate
    └─→ Promote
```

**Key Difference:** Seed strategies skip `pending_review` and go directly to `experiment` status.

---

## 3. How User-Uploaded Strategies Are Connected to Original Uploader

### Connection Mechanism:

**1. Direct Connection (Always Preserved):**
- `user_strategies.user_id` → **Always points to original uploader**
- This field **never changes**, even after mutations
- Used for royalty calculations

**2. Lineage Connection (Tracks Mutations):**
- `strategy_lineage` table tracks parent-child relationships
- Each mutation creates a new `StrategyLineage` record
- Tracks the mutation chain but **does not break the original user_id connection**

### Database Relationships:
```
users
  └─→ user_strategies (user_id FK)  ← Original uploader (ALWAYS preserved)
       ├─→ strategy_lineage (parent_strategy_id)  ← Mutation chain
       └─→ strategy_lineage (child_strategy_id)   ← Mutation chain
```

---

## 4. How Many Mutations Before Parent Connection Is Lost?

**Answer: The parent connection is NEVER lost. The original `user_id` is always preserved.**

### Important Distinction:

1. **Original Uploader Connection (`user_id`):**
   - **NEVER lost** - Always points to the original user who uploaded the strategy
   - Used for royalty calculations
   - Stored in `user_strategies.user_id`

2. **Parent-Child Lineage (`strategy_lineage`):**
   - Tracks the mutation chain (which strategy was mutated from which)
   - Can have infinite generations
   - Used for tracking strategy evolution history
   - Does NOT affect royalty calculations

### Example Mutation Chain:
```
User A uploads Strategy S1
    ↓ (user_id = User A, always)
    
Evolution Worker mutates S1 → S2
    ↓ (S2.user_id = User A, S2 has parent = S1)
    
Evolution Worker mutates S2 → S3
    ↓ (S3.user_id = User A, S3 has parent = S2, grandparent = S1)
    
Evolution Worker mutates S3 → S4
    ↓ (S4.user_id = User A, S4 has parent = S3, grandparent = S2, great-grandparent = S1)
```

**Key Point:** No matter how many mutations, `user_id` always points to User A (original uploader).

---

## 5. Royalty Percentages at Each Mutation Stage

**Answer: Royalty is ALWAYS 5% to the original strategy creator, regardless of mutation generation.**

### Current Royalty Logic:

**Royalty Calculation (from `royalty_service.py`):**
```python
# Royalty rate: 5% for ALL tiers (fixed)
ROYALTY_RATE = 0.05  # 5%

# Calculation:
strategy = get_strategy(trade.strategy_id)
strategy_owner = strategy.user_id  ← Original uploader
royalty = trade_profit * 0.05  ← Always 5% to original uploader
```

### Royalty Flow:
```
User B executes trade using Strategy S4 (mutated 3 times)
    ↓
Trade is profitable: $100 profit
    ↓
System looks up: S4.user_id = User A (original uploader)
    ↓
Royalty Calculation:
    - Royalty: $100 × 5% = $5.00
    - Platform Fee: $5.00 × (creator's plan fee %) = varies
    - Net to User A: $5.00 - platform_fee
```

### Important Notes:

1. **Royalty Always Goes to Original Uploader:**
   - Uses `strategy.user_id` (original uploader)
   - NOT the mutation creator
   - NOT the parent strategy creator

2. **No Royalty Splitting:**
   - The `StrategyLineage` table has `royalty_percent_parent` and `royalty_percent_child` fields
   - **BUT these are NOT currently used in royalty calculations**
   - Current implementation: 100% of royalty goes to original uploader

3. **Platform Fee:**
   - Based on **strategy creator's** subscription plan:
     - Starter: 7% of royalty
     - Pro: 5% of royalty
     - Creator: 3% of royalty

---

## 6. Complete Flow Diagram: User Upload to Mutation

```
┌─────────────────────────────────────────────────────────────────┐
│                    USER UPLOADS STRATEGY                        │
│  User A creates strategy via Strategy Builder UI                │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│              DATABASE: user_strategies                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ id: "strategy-001"                                        │  │
│  │ user_id: "user-a"  ← ORIGINAL UPLOADER (NEVER CHANGES)  │  │
│  │ name: "My Strategy"                                       │  │
│  │ ruleset: {JSON}                                           │  │
│  │ parameters: {JSON}                                         │  │
│  │ status: "pending_review"                                  │  │
│  └──────────────────────────────────────────────────────────┘  │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│              MONITORING WORKER (15 min cycle)                   │
│  1. Check duplicate (fingerprint)                               │
│  2. Run sanity check (lightweight backtest)                     │
│  3. Update status: experiment                                   │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│              DATABASE: user_strategies                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ id: "strategy-001"                                        │  │
│  │ user_id: "user-a"  ← STILL ORIGINAL UPLOADER             │  │
│  │ status: "experiment"                                      │  │
│  │ is_active: true                                           │  │
│  └──────────────────────────────────────────────────────────┘  │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│              EVOLUTION WORKER (8 min cycle)                     │
│  1. Backtest strategy                                           │
│  2. Calculate metrics                                           │
│  3. If underperforming → MUTATE                                 │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MUTATION OCCURS                              │
│  Evolution Worker creates Strategy S2 from S1                   │
└───────────────────────┬─────────────────────────────────────────┘
                        │
        ┌───────────────┴───────────────┐
        │                               │
        ▼                               ▼
┌───────────────────┐         ┌───────────────────────────────────┐
│ user_strategies   │         │ strategy_lineage                 │
│ ┌───────────────┐ │         │ ┌─────────────────────────────┐ │
│ │ id: "s2"      │ │         │ │ parent_strategy_id: "s1"   │ │
│ │ user_id: "a"  │◄┼─────────┼─┤ child_strategy_id: "s2"    │ │
│ │ name: "S1..." │ │         │ │ mutation_type: "param..."  │ │
│ │ status: "exp"  │ │         │ │ creator_user_id: "a"       │ │
│ └───────────────┘ │         │ └─────────────────────────────┘ │
└───────────────────┘         └───────────────────────────────────┘
        │
        │ (S2 still has user_id = "a")
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│              MUTATION 2: S2 → S3                                │
└───────────────────────┬─────────────────────────────────────────┘
        │
        ▼
┌───────────────────┐         ┌───────────────────────────────────┐
│ user_strategies   │         │ strategy_lineage                  │
│ ┌───────────────┐ │         │ ┌─────────────────────────────┐ │
│ │ id: "s3"      │ │         │ │ parent: "s2"                │ │
│ │ user_id: "a"  │◄┼─────────┼─┤ child: "s3"                 │ │
│ └───────────────┘ │         │ │ (chain: s1 → s2 → s3)       │ │
└───────────────────┘         │ └─────────────────────────────┘ │
                              └───────────────────────────────────┘
        │
        │ (S3 still has user_id = "a")
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│              USER B EXECUTES TRADE USING S3                     │
│  Trade profit: $100                                              │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│              ROYALTY CALCULATION                                │
│  1. Look up S3.user_id = "user-a" (original uploader)          │
│  2. Calculate: $100 × 5% = $5.00                                │
│  3. Platform fee: $5.00 × (User A's plan fee %)                │
│  4. Net to User A: $5.00 - platform_fee                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Summary

### Key Points:

1. **Storage:** Strategies are saved in PostgreSQL database (JSON columns), NOT as files
2. **Checks:** Both seeded and user-uploaded strategies go through Monitoring Worker and Evolution Worker
3. **Connection:** `user_id` field always points to original uploader (never changes)
4. **Mutations:** Parent connection via lineage is tracked but doesn't affect `user_id`
5. **Royalties:** Always 5% to original uploader, regardless of mutation generation
6. **Lineage:** Tracks mutation chain but doesn't split royalties

### Current Implementation Gaps:

1. **Royalty Splitting Not Implemented:**
   - `StrategyLineage.royalty_percent_parent` and `royalty_percent_child` exist but are not used
   - All royalties go to original uploader
   - No logic to split royalties between parent and child creators

2. **No Generation Limit:**
   - Lineage can track infinite generations
   - No logic to "lose" connection after N mutations
   - Original `user_id` is always preserved

### Recommendations:

If you want to implement royalty splitting:
1. Add logic to calculate royalty split based on mutation generation
2. Use `StrategyLineage.royalty_percent_parent` and `royalty_percent_child`
3. Traverse lineage chain to split royalties between all ancestors
4. Example: Generation 1 (original) gets 50%, Generation 2 gets 30%, Generation 3 gets 20%

