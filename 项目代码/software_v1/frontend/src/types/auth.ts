export interface LoginRequest { username: string; password: string }
export interface LoginResponse { user_id: number; username: string; role: string; access_token: string; token_type: 'bearer'; expires_at: string }
export interface CurrentUserResponse { user_id: number; username: string; display_name: string | null; role: string; status: string; last_login_at: string | null }
export interface PasswordChangeRequest { current_password: string; new_password: string }
export interface UserCreateRequest { username: string; display_name?: string; password: string; role: 'reviewer' | 'operator' }
export interface UserResponse { user_id: number; username: string; display_name: string | null; role: string; status: string; created_at: string }
