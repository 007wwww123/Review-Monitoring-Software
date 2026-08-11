export interface LoginRequest { username: string; password: string }
export interface LoginResponse { user_id: number; username: string; role: string; access_token: string; token_type: 'bearer'; expires_at: string }
