import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

export async function GET() {
  try {
    const settings = await prisma.adminSetting.findMany({
      orderBy: { key: 'asc' },
    });

    if (settings.length === 0) {
      const mockSettings = [
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

      return NextResponse.json({ settings: mockSettings, isMock: true });
    }

    return NextResponse.json({ settings });
  } catch (error) {
    console.error('Error fetching admin settings:', error);

    const mockSettings = [
      { key: 'USER_PRICE_MONTHLY', value: '3999' },
      { key: 'PRO_PRICE_MONTHLY', value: '4999' },
      { key: 'CREATOR_PRICE_MONTHLY', value: '9999' },
      { key: 'USER_PERFORMANCE_FEE', value: '5.0' },
      { key: 'PRO_PERFORMANCE_FEE', value: '3.0' },
      { key: 'CREATOR_PERFORMANCE_FEE', value: '3.0' },
    ];

    return NextResponse.json({ settings: mockSettings, isMock: true });
  }
}

export async function PATCH(request: Request) {
  try {
    const body = await request.json();
    const { key, value } = body;

    if (!key || value === undefined) {
      return NextResponse.json(
        { error: 'Key and value are required' },
        { status: 400 }
      );
    }

    const setting = await prisma.adminSetting.upsert({
      where: { key },
      update: { value: String(value) },
      create: { key, value: String(value) },
    });

    return NextResponse.json({ setting });
  } catch (error) {
    console.error('Error updating admin setting:', error);
    return NextResponse.json({ error: 'Failed to update setting' }, { status: 500 });
  }
}
