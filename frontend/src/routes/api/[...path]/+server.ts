// Forwards /api/* to the FastAPI backend, so the browser only talks to this origin.
import type { RequestHandler } from './$types';

const API_URL = process.env.API_URL ?? 'http://localhost:8000';

const proxy: RequestHandler = async ({ params, url, request, fetch }) => {
	const target = `${API_URL}/api/${params.path}${url.search}`;
	const res = await fetch(target, {
		method: request.method,
		headers: { 'content-type': request.headers.get('content-type') ?? 'application/json' },
		body: request.method === 'GET' ? undefined : await request.text()
	});
	return new Response(res.body, {
		status: res.status,
		headers: { 'content-type': res.headers.get('content-type') ?? 'application/json' }
	});
};

export const GET = proxy;
export const POST = proxy;
