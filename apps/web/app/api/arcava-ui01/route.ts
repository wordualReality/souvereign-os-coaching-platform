import { NextRequest } from "next/server";
import { fixturePost } from "./bridge";
export { GET } from "./bridge";

export const dynamic = "force-dynamic";

export function POST(request: NextRequest) {
  return fixturePost(request);
}
