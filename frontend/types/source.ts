export interface Source {
  id: number;
  linkedin_url: string;
  label: string | null;
  created_at: string;
}

export interface SourceCreate {
  linkedin_url: string;
  label?: string;
}
