import { NextResponse } from 'next/server';

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { symbol, side, quantity, orderType, limitPrice, mode } = body;

    if (!symbol || !side || !quantity || !mode) {
      return NextResponse.json(
        { error: 'Missing required fields' },
        { status: 400 }
      );
    }

    console.log('Placing order:', {
      symbol,
      side,
      quantity,
      orderType,
      limitPrice,
      mode,
    });

    if (mode === 'paper') {
      const mockOrder = {
        id: `order_${Date.now()}`,
        symbol,
        side,
        quantity,
        orderType,
        limitPrice,
        mode,
        status: 'filled',
        filledAt: new Date().toISOString(),
        fillPrice: orderType === 'market' ? 150.25 : limitPrice,
      };

      return NextResponse.json({
        success: true,
        order: mockOrder,
        message: `Paper ${orderType} ${side} order placed successfully`,
      });
    }

    if (mode === 'real') {
      return NextResponse.json({
        success: true,
        order: {
          id: `order_${Date.now()}`,
          symbol,
          side,
          quantity,
          orderType,
          mode,
          status: 'pending',
        },
        message: `Real ${orderType} ${side} order submitted to broker`,
      });
    }

    return NextResponse.json(
      { error: 'Invalid trading mode' },
      { status: 400 }
    );
  } catch (error) {
    console.error('Error placing order:', error);
    return NextResponse.json(
      { error: 'Failed to place order' },
      { status: 500 }
    );
  }
}
