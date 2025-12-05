import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const ownerId = searchParams.get('ownerId');
    const visibility = searchParams.get('visibility');

    const strategies = await prisma.strategyMeta.findMany({
      where: {
        ...(ownerId && { ownerId }),
        ...(visibility && { visibility: visibility as any }),
      },
      include: {
        owner: {
          select: {
            id: true,
            name: true,
            email: true,
            role: true,
          },
        },
        royalties: {
          select: {
            totalProfitGenerated: true,
            totalRoyaltyPaid: true,
          },
        },
      },
      orderBy: { createdAt: 'desc' },
    });

    return NextResponse.json({ strategies });
  } catch (error) {
    console.error('Error fetching strategies:', error);

    const mockStrategies = [
      {
        id: 'mock-strategy-1',
        name: 'Momentum Breakout V2',
        visibility: 'PUBLIC',
        isCreatorOnly: false,
        ownerId: 'mock-user-1',
        summaryStatsJson: {
          winRate: 68.5,
          totalTrades: 245,
          avgReturn: 2.3,
        },
        owner: {
          id: 'mock-user-1',
          name: 'Jane Smith',
          email: 'jane@example.com',
          role: 'CREATOR',
        },
      },
    ];

    return NextResponse.json({ strategies: mockStrategies, isMock: true });
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { ownerId, name, visibility, isCreatorOnly, summaryStatsJson } = body;

    const strategy = await prisma.strategyMeta.create({
      data: {
        ownerId,
        name,
        visibility: visibility || 'PRIVATE',
        isCreatorOnly: isCreatorOnly || false,
        summaryStatsJson,
      },
      include: {
        owner: {
          select: {
            id: true,
            name: true,
            email: true,
          },
        },
      },
    });

    return NextResponse.json({ strategy });
  } catch (error) {
    console.error('Error creating strategy:', error);
    return NextResponse.json({ error: 'Failed to create strategy' }, { status: 500 });
  }
}
