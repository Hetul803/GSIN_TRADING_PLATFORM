import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

export async function GET() {
  try {
    // Call the Python backend API
    const response = await fetch(`${BACKEND_URL}/subscriptions/plans`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Backend returned ${response.status}`);
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching subscription plans:', error);

    // Fallback to mock data if backend is unavailable
    const mockPlans = [
      {
        id: 'mock-user',
        planCode: 'USER',
        name: 'User',
        priceMonthly: 3999,
        defaultRoyaltyPercent: 5.0,
        description: 'Perfect for individual traders. Can use strategies and signals.',
        isCreatorPlan: false,
        isActive: true,
      },
      {
        id: 'mock-user-upload',
        planCode: 'USER_PLUS_UPLOAD',
        name: 'User + Upload',
        priceMonthly: 4999,
        defaultRoyaltyPercent: 5.0,
        description: 'Everything in User plan, plus upload strategies and earn royalties.',
        isCreatorPlan: false,
        isActive: true,
      },
      {
        id: 'mock-creator',
        planCode: 'CREATOR',
        name: 'Creator',
        priceMonthly: 9999,
        defaultRoyaltyPercent: 3.0,
        description: 'Content creator account with better royalty rates and all features.',
        isCreatorPlan: true,
        isActive: true,
      },
    ];

    return NextResponse.json({ plans: mockPlans, isMock: true });
  }
}
