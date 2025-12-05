import { NextResponse } from 'next/server';

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { provider, apiKey, apiSecret } = body;

    if (!provider || !apiKey || !apiSecret) {
      return NextResponse.json(
        { error: 'Missing required fields' },
        { status: 400 }
      );
    }

    console.log('Connecting to broker:', provider);

    if (provider === 'alpaca') {
      const mockConnection = {
        provider: 'alpaca',
        isConnected: true,
        connectedAt: new Date().toISOString(),
        accountInfo: {
          accountNumber: 'MOCK123456',
          buyingPower: 100000,
          cash: 100000,
        },
      };

      return NextResponse.json({
        success: true,
        connection: mockConnection,
        message: 'Successfully connected to Alpaca (mock)',
      });
    }

    return NextResponse.json(
      { error: 'Unsupported broker provider' },
      { status: 400 }
    );
  } catch (error) {
    console.error('Error connecting to broker:', error);
    return NextResponse.json(
      { error: 'Failed to connect to broker' },
      { status: 500 }
    );
  }
}
