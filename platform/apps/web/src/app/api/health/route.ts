import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

export function GET() {
  return NextResponse.json(
    { status: 'ok', service: 'aisearcharab-web', phase: 'sprint-0' },
    { headers: { 'Cache-Control': 'no-store' } },
  );
}
