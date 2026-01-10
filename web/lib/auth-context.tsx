"use client";

import { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { api, User } from "./api";

interface AuthContextType {
    user: User | null;
    isLoading: boolean;
    isAuthenticated: boolean;
    login: (user: User) => void;
    logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const STORAGE_KEY = "open-rabbit-user";

export function AuthProvider({ children }: { children: ReactNode }) {
    const [user, setUser] = useState<User | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        // Check localStorage for existing session
        const storedUser = localStorage.getItem(STORAGE_KEY);
        if (storedUser) {
            try {
                const parsed = JSON.parse(storedUser);
                setUser(parsed);
            } catch {
                localStorage.removeItem(STORAGE_KEY);
            }
        }
        setIsLoading(false);
    }, []);

    const login = (userData: User) => {
        setUser(userData);
        localStorage.setItem(STORAGE_KEY, JSON.stringify(userData));
        // Set cookie for middleware auth check
        document.cookie = `open-rabbit-auth=true; path=/; max-age=${60 * 60 * 24 * 7}`; // 7 days
    };

    const logout = () => {
        setUser(null);
        localStorage.removeItem(STORAGE_KEY);
        // Remove auth cookie
        document.cookie = 'open-rabbit-auth=; path=/; max-age=0';
    };

    return (
        <AuthContext.Provider
            value={{
                user,
                isLoading,
                isAuthenticated: !!user,
                login,
                logout,
            }}
        >
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error("useAuth must be used within an AuthProvider");
    }
    return context;
}

export { api };
