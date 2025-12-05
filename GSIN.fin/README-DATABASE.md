# GSIN Database Setup Guide

## Overview

This GSIN application now uses **Prisma ORM** with **PostgreSQL** to manage frontend-facing data including users, subscriptions, groups, strategies, and admin settings.

## Database Schema

The Prisma schema includes the following models:

### Core Models

1. **User** - User accounts and profiles
   - `id`, `email`, `name`, `role`, `subscriptionTier`
   - Relations: subscriptions, strategies, groups

2. **SubscriptionPlan** - Available subscription tiers
   - User ($39.99/mo, 5% performance fee)
   - Pro ($49.99/mo, 3% performance fee)
   - Creator ($99.99/mo, 3% performance fee)

3. **UserSubscription** - Active user subscriptions
   - Links users to plans with billing periods and trial info

4. **StrategyMeta** - Strategy metadata and summary stats
   - Stores strategy info, visibility, and backtest summaries
   - Does NOT store heavy trading logs (those go to Python backend)

5. **Group** - Trading communities
   - Group info, pricing, discoverability settings
   - Invite codes for private groups

6. **GroupMember** - Group membership records
   - User roles: OWNER, MODERATOR, MEMBER

7. **AdminSetting** - System-wide configuration
   - Key-value store for pricing, fees, limits

8. **RoyaltySummary** - Creator earnings tracking
   - Tracks profit and royalties per strategy

## Setup Instructions

### 1. Configure Database Connection

Update your `.env` file with a real PostgreSQL connection:

```env
DATABASE_URL="postgresql://username:password@host:5432/database?schema=public"
```

**Current placeholder:**
```env
DATABASE_URL="postgresql://postgres:password@localhost:5432/gsin?schema=public"
```

### 2. Generate Prisma Client

```bash
npm run db:generate
```

### 3. Push Schema to Database

```bash
npm run db:push
```

This creates all tables without running migrations (good for development).

### 4. Seed Initial Data

```bash
npm run db:seed
```

This creates:
- 3 subscription plans (User, Pro, Creator)
- Admin settings for pricing and limits

## API Routes

All database operations happen through Next.js API routes:

### Subscriptions
- `GET /api/subscriptions/plans` - List all plans
- `POST /api/subscriptions/plans` - Create new plan (admin)

### Groups
- `GET /api/groups?userId={id}` - List user's groups
- `POST /api/groups` - Create new group
- `GET /api/groups/[groupId]` - Get group details
- `PATCH /api/groups/[groupId]` - Update group
- `DELETE /api/groups/[groupId]` - Delete group

### Strategies
- `GET /api/strategies?ownerId={id}` - List strategies
- `POST /api/strategies` - Create strategy metadata

### Admin Settings
- `GET /api/admin/settings` - Get all settings
- `PATCH /api/admin/settings` - Update setting

## Graceful Fallback

The app is designed to work even without a database connection:

1. API routes return mock data if DB is unavailable
2. All queries are wrapped in try-catch blocks
3. Mock data matches the schema structure
4. Clear console warnings when using mock data

### Example (from `/lib/prisma.ts`):

```typescript
export async function getSubscriptionPlans() {
  try {
    const plans = await prisma.subscriptionPlan.findMany();
    return plans.length > 0 ? plans : getMockSubscriptionPlans();
  } catch (error) {
    console.error('DB error, using mock data');
    return getMockSubscriptionPlans();
  }
}
```

## Using in Pages

### Example: Subscriptions Page

```typescript
// app/subscriptions/page.tsx
const [plans, setPlans] = useState<SubscriptionPlan[]>([]);

useEffect(() => {
  async function loadPlans() {
    const response = await fetch('/api/subscriptions/plans');
    const data = await response.json();
    setPlans(data.plans);
  }
  loadPlans();
}, []);
```

## Migration Commands

```bash
# Generate Prisma client
npm run db:generate

# Push schema (no migrations)
npx prisma db push

# Create migration
npx prisma migrate dev --name your_migration_name

# Run seed
npm run db:seed

# Open Prisma Studio (DB GUI)
npx prisma studio
```

## Important Notes

1. **Heavy data stays in Python backend** - This DB only stores:
   - User profiles and auth
   - Subscription billing info
   - Strategy metadata (not full backtest logs)
   - Group membership
   - Admin settings

2. **Mock data available** - All pages work without DB connection

3. **No breaking changes** - Existing auth and UI remain intact

4. **Production ready** - Just replace `DATABASE_URL` with real Postgres connection

## Next Steps

- [ ] Connect to production Postgres database
- [ ] Run `npm run db:push` to create tables
- [ ] Run `npm run db:seed` to add initial data
- [ ] Verify API routes return real data
- [ ] Set up backup strategy
- [ ] Configure connection pooling for production
