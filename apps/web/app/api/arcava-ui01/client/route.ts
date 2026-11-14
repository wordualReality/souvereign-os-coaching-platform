import { NextRequest } from "next/server";
import { fixturePost } from "../bridge";

export function POST(request: NextRequest) {
  return fixturePost(request, "client");
}
