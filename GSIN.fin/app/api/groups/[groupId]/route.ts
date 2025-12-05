import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

export async function GET(
  request: Request,
  { params }: { params: { groupId: string } }
) {
  try {
    const group = await prisma.group.findUnique({
      where: { id: params.groupId },
      include: {
        owner: {
          select: {
            id: true,
            name: true,
            email: true,
            role: true,
          },
        },
        members: {
          where: { isActive: true },
          include: {
            user: {
              select: {
                id: true,
                name: true,
                email: true,
                role: true,
              },
            },
          },
          orderBy: { joinedAt: 'asc' },
        },
      },
    });

    if (!group) {
      return NextResponse.json({ error: 'Group not found' }, { status: 404 });
    }

    return NextResponse.json({ group });
  } catch (error) {
    console.error('Error fetching group:', error);
    return NextResponse.json({ error: 'Failed to fetch group' }, { status: 500 });
  }
}

export async function PATCH(
  request: Request,
  { params }: { params: { groupId: string } }
) {
  try {
    const body = await request.json();
    const { name, description, maxSize, isDiscoverable, isPaid, priceMonthly } = body;

    const group = await prisma.group.update({
      where: { id: params.groupId },
      data: {
        ...(name && { name }),
        ...(description && { description }),
        ...(maxSize !== undefined && { maxSize }),
        ...(isDiscoverable !== undefined && { isDiscoverable }),
        ...(isPaid !== undefined && { isPaid }),
        ...(priceMonthly !== undefined && { priceMonthly }),
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

    return NextResponse.json({ group });
  } catch (error) {
    console.error('Error updating group:', error);
    return NextResponse.json({ error: 'Failed to update group' }, { status: 500 });
  }
}

export async function DELETE(
  request: Request,
  { params }: { params: { groupId: string } }
) {
  try {
    await prisma.group.delete({
      where: { id: params.groupId },
    });

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Error deleting group:', error);
    return NextResponse.json({ error: 'Failed to delete group' }, { status: 500 });
  }
}
