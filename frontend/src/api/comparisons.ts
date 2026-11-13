import {request,post} from './client';import type {ComparisonStudy,ComparisonRun} from '../types/domain';
export const listStudies=()=>request<ComparisonStudy[]>('/comparison-studies');
export const createStudy=(data:unknown)=>post<ComparisonStudy>('/comparison-studies',data);
export const listRuns=()=>request<ComparisonRun[]>('/comparison-runs');
export const createRun=(data:unknown)=>post<ComparisonRun>('/comparison-runs',data);
