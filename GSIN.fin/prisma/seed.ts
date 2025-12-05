import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

async function main() {
  console.log('Starting database seed...');

  const existingPlans = await prisma.subscriptionPlan.findMany();
  if (existingPlans.length > 0) {
    console.log('Subscription plans already exist, skipping seed.');
    return;
  }

  const userPlan = await prisma.subscriptionPlan.create({
    data: {
      name: 'User',
      priceMonthly: 3999,
      performanceFeePercent: 5.0,
      isCreatorPlan: false,
      description: 'Perfect for individual traders getting started with the platform',
      isActive: true,
    },
  });

  const proPlan = await prisma.subscriptionPlan.create({
    data: {
      name: 'Pro',
      priceMonthly: 4999,
      performanceFeePercent: 3.0,
      isCreatorPlan: false,
      description: 'Advanced features and tools for serious traders',
      isActive: true,
    },
  });

  const creatorPlan = await prisma.subscriptionPlan.create({
    data: {
      name: 'Creator',
      priceMonthly: 9999,
      performanceFeePercent: 3.0,
      isCreatorPlan: true,
      description: 'Build, monetize, and share your trading strategies',
      isActive: true,
    },
  });

  console.log('Created subscription plans:', { userPlan, proPlan, creatorPlan });

  const adminSettings = [
    { key: 'USER_PRICE_MONTHLY', value: '3999' },
    { key: 'PRO_PRICE_MONTHLY', value: '4999' },
    { key: 'CREATOR_PRICE_MONTHLY', value: '9999' },
    { key: 'USER_PERFORMANCE_FEE', value: '5.0' },
    { key: 'PRO_PERFORMANCE_FEE', value: '3.0' },
    { key: 'CREATOR_PERFORMANCE_FEE', value: '3.0' },
    { key: 'GROUP_REVENUE_SHARE', value: '20.0' },
    { key: 'TRIAL_DAYS', value: '14' },
    { key: 'MAX_STRATEGIES_USER', value: '5' },
    { key: 'MAX_STRATEGIES_PRO', value: '25' },
    { key: 'MAX_STRATEGIES_CREATOR', value: '100' },
  ];

  for (const setting of adminSettings) {
    await prisma.adminSetting.upsert({
      where: { key: setting.key },
      update: { value: setting.value },
      create: setting,
    });
  }

  console.log('Created admin settings');

  console.log('Seed completed successfully!');
}

main()
  .catch((e) => {
    console.error('Error during seed:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
