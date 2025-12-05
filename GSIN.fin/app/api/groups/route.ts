import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const userId = searchParams.get('userId');

    const groups = await prisma.group.findMany({
      where: userId
        ? {
            OR: [
              { ownerId: userId },
              {
                members: {
                  some: {
                    userId: userId,
                    isActive: true,
                  },
                },
              },
            ],
          }
        : { isDiscoverable: true },
      include: {
        owner: {
          select: {
            id: true,
            name: true,
            email: true,
          },
        },
        members: {
          where: { isActive: true },
          select: {
            id: true,
            role: true,
            user: {
              select: {
                id: true,
                name: true,
                email: true,
              },
            },
          },
        },
      },
      orderBy: { createdAt: 'desc' },
    });

    return NextResponse.json({ groups });
  } catch (error) {
    console.error('Error fetching groups:', error);

    const mockGroups = [
      {
        id: 'mock-group-1',
        name: 'Day Traders United',
        description: 'Community of active day traders sharing strategies',
        ownerId: 'mock-user-1',
        maxSize: 50,
        isDiscoverable: true,
        isPaid: false,
        members: [],
        owner: { id: 'mock-user-1', name: 'John Doe', email: 'john@example.com' },
      },
    ];

    return NextResponse.json({ groups: mockGroups, isMock: true });
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { ownerId, name, description, maxSize, isDiscoverable, isPaid, priceMonthly } = body;

    const group = await prisma.group.create({
      data: {
        ownerId,
        name,
        description,
        maxSize,
        isDiscoverable: isDiscoverable || false,
        isPaid: isPaid || false,
        priceMonthly,
        inviteCode: Math.random().toString(36).substring(2, 10).toUpperCase(),
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

    await prisma.groupMember.create({
      data: {
        groupId: group.id,
        userId: ownerId,
        role: 'OWNER',
      },
    });

    return NextResponse.json({ group });
  } catch (error) {
    console.error('Error creating group:', error);
    return NextResponse.json({ error: 'Failed to create group' }, { status: 500 });
  }
}
