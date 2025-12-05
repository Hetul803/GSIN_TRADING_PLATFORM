import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const mode = searchParams.get('mode') || 'PAPER';
    const symbol = searchParams.get('symbol');
    const userId = request.headers.get('X-User-Id');

    if (!userId) {
      return NextResponse.json(
        { error: 'User ID required', trades: [], total: 0 },
        { status: 401 }
      );
    }

    // Forward request to backend
    const url = new URL(`${BACKEND_URL}/api/trades`);
    if (mode) url.searchParams.set('mode', mode);
    if (symbol) url.searchParams.set('symbol', symbol);

    const response = await fetch(url.toString(), {
      headers: {
        'X-User-Id': userId,
      },
    });

    if (!response.ok) {
      throw new Error(`Backend error: ${response.statusText}`);
    }

    const data = await response.json();
    return NextResponse.json({
      trades: data || [],
      total: Array.isArray(data) ? data.length : 0,
    });
  } catch (error) {
    console.error('Error fetching trade history:', error);
    return NextResponse.json({
      trades: [],
      total: 0,
      error: 'Failed to fetch trade history',
    }, { status: 500 });
  }
}
